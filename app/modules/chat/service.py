from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from uuid import UUID


from db.relational.schemas import ConversationCreate, MessageCreate
from db.relational.models.conversation import Conversation
from db.relational.constants import MessageRole

from modules.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationMetadata,
    MessageMetadata,
)

from shared.tracing import observe

from modules.chat.utils.asset import save_attachment

from modules.chat.schemas import Attachment

from modules.chat.schemas import CitedSource

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from db.relational.repositories.conversation_repository import AsyncConversationRepository
    from db.relational.repositories.message_repository import AsyncMessageRepository
    from modules.chat.conversation_manager import ConversationManager
    from db.relational.schemas import ConversationUpdate
    from modules.chat.dependencies import ValidatedAttachment
    from modules.chat.attachment_processor import AttachmentProcessor
    

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        conversation_repo:   AsyncConversationRepository,
        message_repo:        AsyncMessageRepository,
        convesation_manager: ConversationManager,
        file_processor:      AttachmentProcessor,
        settings:            ChatSettings,
        agent_loop_factory,
    ):
        self._conv_repo          = conversation_repo
        self._message_repo       = message_repo
        self._conv_manager       = convesation_manager
        self._file_processor     = file_processor
        self._settings           = settings
        self._agent_loop_factory = agent_loop_factory

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    async def add_conversation(self, data: ConversationCreate, user_id: UUID) -> ConversationMetadata:
        conv = await self._conv_repo.add(data=data, user_id=user_id)
        return ConversationMetadata(id=conv.id, name=conv.name)

    async def list_conversations(self, user_id: UUID) -> list[ConversationMetadata]:
        conversations = await self._conv_repo.get_all_by_user(user_id=user_id)
        return [ConversationMetadata(id=c.id, name=c.name) for c in conversations]

    async def update_conversation(self, data: ConversationUpdate, conv: Conversation) -> ConversationMetadata:
        conv = await self._conv_repo.update(data=data, conversation=conv)
        return ConversationMetadata(id=conv.id, name=conv.name)

    async def delete_conversation(self, conv: Conversation) -> None:
        await self._conv_repo.delete(conv)

    async def list_messages(self, id: UUID) -> list[MessageMetadata]:
        messages = await self._message_repo.get_all_by_conversation(id)
        return [MessageMetadata(role=m.role, content=m.content) for m in messages]



    # ------------------------------------------------------------------
    # chat
    # ------------------------------------------------------------------
    async def attach_documents(
        self,
        attachments: list[ValidatedAttachment]
    ) -> list[Attachment]:
        
        saved_attachments = []

        for attachment in attachments:
            attachment_id = await save_attachment(
                name=attachment.name, 
                file=attachment.file,
            )
            saved_attachments.append(Attachment(
                id=attachment_id,
                type=attachment.type,
            ))

        return saved_attachments


    async def chat(self, conv: Conversation, request: ChatRequest) -> ChatResponse:
        raw_history     = await self._message_repo.get_all_by_conversation(conv.id)
        trimmed_history = self._conv_manager.trim_history(raw_history)

        attachment_contents: list[str] = []
        if request.attachments:
            with observe(
                name="attachments_extraction",
                input={"attachments_ids": [str(a.id) for a in request.attachments]},
            ) as span:
                attachment_contents = await self._file_processor.process(request.attachments, request.query)
                await self._file_processor.cleanup(request.attachments)
                span.update(output={
                    "attachments": [
                        {
                            "chars":           len(a),
                            "has_content":     a != "NO_ITEMS_FOUND",
                            "content_preview": a[:500],
                        }
                        for a in attachment_contents
                    ]
                })

        answer, sources = await self._run_agent(
            request=request,
            conv=conv,
            history=trimmed_history,
            attachment_contents=attachment_contents,
        )

        await self._message_repo.add(
            data=MessageCreate(
                role=MessageRole.user,
                content=request.query,
            ),
            conversation_id=conv.id,
        )
        await self._message_repo.add(
            data=MessageCreate(
                role=MessageRole.assistant,
                content=answer,
            ),
            conversation_id=conv.id,
        )

        return ChatResponse(
            answer=answer,
            sources=sources,
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        request:         ChatRequest,
        conv:            Conversation,
        history:         list,
        attachment_contents: list[str] | None = None,
    ) -> tuple[str, list[CitedSource]]:
        agent_loop = self._agent_loop_factory(
            user_id=conv.user_id,
            course_id=conv.meta.course_id,
            documents_ids=conv.meta.documents_ids,
        )

        result = await agent_loop.run(
            user_query=request.query,
            attachment_contents=attachment_contents,
            history=history,
            trace_metadata={
                "conversation_id": str(conv.id),
                "user_id":         str(conv.user_id),
                "course_id":       str(conv.meta.course_id),
            },
        )

        if result.hit_limit:
            logger.warning("ChatService: agent hit iteration limit for conv %s", conv.id)

        return result.answer, result.cited_sources
