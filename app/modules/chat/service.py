from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from modules.chat.file_processor import FileProcessor
from db.relational.schemas import ConversationCreate, MessageCreate
from db.relational.models.conversation import Conversation
from db.relational.constants import MessageRole

from modules.chat.schemas import (
    ChatRequest,
    ChatResponse,
    CitedSource,
    ConversationHistoryResponse,
    ConversationMetadata,
    FileExtractionResult,
)
from shared.tracing import observe

if TYPE_CHECKING:
    from modules.chat.config import ChatSettings
    from db.relational.repositories.conversation_repository import AsyncConversationRepository
    from db.relational.repositories.message_repository import AsyncMessageRepository
    from modules.chat.conversation import ConversationManager
    from db.relational.schemas import ConversationUpdate

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        conversation_repo:   AsyncConversationRepository,
        message_repo:        AsyncMessageRepository,
        convesation_manager: ConversationManager,
        file_processor:      FileProcessor,
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
    # Conversation CRUD
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

    # ------------------------------------------------------------------
    # Core chat turn
    # ------------------------------------------------------------------

    async def chat(self, conv: Conversation, request: ChatRequest) -> ChatResponse:
        raw_history     = await self._message_repo.get_all_by_conversation(conv.id)
        trimmed_history = self._conv_manager.trim_history(raw_history)

        # ── File extraction — traced with full content preview ────────────
        extracted_files: list[FileExtractionResult] = []
        if request.files:
            with observe(
                name="file_extraction",
                input={"file_ids": [str(f) for f in request.files]},
            ) as span:
                extracted_files = await self._file_processor.process(request.files, request.query)
                await self._file_processor.cleanup(request.files)
                span.update(output={
                    "files": [
                        {
                            "id":              str(f.file_id),
                            "type":            str(f.file_type),
                            "chars":           len(f.markdown_content),
                            "has_content":     f.markdown_content != "NO_ITEMS_FOUND",
                            "content_preview": f.markdown_content[:5000],
                        }
                        for f in extracted_files
                    ]
                })

        answer, sources, prompt_tokens, completion_tokens = await self._run_agent(
            request=request,
            conv=conv,
            history=trimmed_history,
            extracted_files=extracted_files,
        )

        await self._message_repo.add(
            data=MessageCreate(
                role=MessageRole.user,
                content=request.query,
                token_count=prompt_tokens,
            ),
            conversation_id=conv.id,
        )
        await self._message_repo.add(
            data=MessageCreate(
                role=MessageRole.assistant,
                content=answer,
                token_count=completion_tokens,
            ),
            conversation_id=conv.id,
        )

        return ChatResponse(
            answer=answer,
            sources=sources,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def get_history(self, id: UUID) -> ConversationHistoryResponse:
        messages = await self._message_repo.get_all_by_conversation(id)
        return ConversationHistoryResponse(
            conversation_id=str(id),
            messages=messages,  # type: ignore[arg-type]
            total=len(messages),
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        request:         ChatRequest,
        conv:            Conversation,
        history:         list,
        extracted_files: list[FileExtractionResult] | None = None,
    ) -> tuple[str, list[CitedSource], int | None, int | None]:
        agent_loop = self._agent_loop_factory(
            user_id=conv.user_id,
            course_id=conv.meta.course_id,
            documents_ids=conv.meta.documents_ids,
        )

        result = await agent_loop.run(
            user_query=request.query,
            extracted_files=extracted_files,
            history=self._orm_history_to_lc(history),
            trace_metadata={
                "conversation_id": str(conv.id),
                "user_id":         str(conv.user_id),
                "course_id":       str(conv.meta.course_id),
            },
        )

        if result.hit_limit:
            logger.warning("ChatService: agent hit iteration limit for conv %s", conv.id)

        return result.answer, result.cited_sources, None, None

    @staticmethod
    def _orm_history_to_lc(history: list) -> list[BaseMessage]:
        lc: list[BaseMessage] = []
        for msg in history:
            if msg.role == MessageRole.user:
                lc.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                lc.append(AIMessage(content=msg.content))
        return lc