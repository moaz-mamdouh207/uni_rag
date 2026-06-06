from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status, Depends

from core.config import settings
from shared.constants import ErrorMessages

from modules.chat.service import ChatService
from modules.chat.agent.loop import AgentLoop
from modules.chat.agent.tools import AgentTools
from modules.chat.file_processor import FileProcessor

from db.relational.session import get_async_db
from modules.retrieval.dependencies import get_retrieval_service
from shared.llm.dependencies import get_llm_client
from modules.auth.dependencies import get_current_user

from db.relational.repositories.conversation_repository import AsyncConversationRepository
from db.relational.repositories.message_repository import AsyncMessageRepository

from modules.chat.conversation import ConversationManager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from modules.retrieval.service import RetrievalService
    from shared.llm.client import LLMClient
    from db.relational.models.user import User
    from db.relational.models.conversation import Conversation


def get_chat_service(
    db:                AsyncSession     = Depends(get_async_db),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    llm_client:        LLMClient        = Depends(get_llm_client),
) -> ChatService:

    def agent_loop_factory(
        user_id:       UUID,
        course_id:     UUID,
        documents_ids: list[UUID] | None = None,
    ) -> AgentLoop:
        tools = AgentTools(
            retrieval_service=retrieval_service,
            settings=settings.chat,
            user_id=user_id,
            course_id=course_id,
            documents_ids=documents_ids,
        )
        return AgentLoop(
            llm=llm_client.get_llm(),
            tools=tools,
            max_iterations=settings.chat.max_agent_iterations,
        )

    return ChatService(
        conversation_repo=AsyncConversationRepository(db),
        message_repo=AsyncMessageRepository(db),
        convesation_manager=ConversationManager(settings.chat),
        file_processor=FileProcessor(llm_client, settings.chat),
        settings=settings.chat,
        agent_loop_factory=agent_loop_factory,
    )


async def get_current_conv(
    conversation_id: UUID,
    user: User         = Depends(get_current_user),
    db:   AsyncSession = Depends(get_async_db),
) -> Conversation:
    conversation_repo = AsyncConversationRepository(db)
    conversation = await conversation_repo.get_by_id(conversation_id=conversation_id)
    if conversation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorMessages.FORBIDDEN_ACCESS,
        )
    return conversation