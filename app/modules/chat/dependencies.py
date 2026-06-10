from __future__ import annotations
from typing import TYPE_CHECKING, BinaryIO
from uuid import UUID
from dataclasses import dataclass
import asyncio
import logging
import os
import magic

from fastapi import HTTPException, status, Depends, UploadFile

from core.config import settings
from shared.constants import ErrorMessages

from modules.chat.service import ChatService
from modules.chat.agent.loop import AgentLoop
from modules.chat.agent.tools import AgentTools
from modules.chat.attachment_processor import AttachmentProcessor

from db.relational.session import get_async_db
from modules.retrieval.dependencies import get_retrieval_service
from shared.llm.dependencies import get_llm_client
from modules.auth.dependencies import get_current_user

from db.relational.repositories.conversation_repository import AsyncConversationRepository
from db.relational.repositories.message_repository import AsyncMessageRepository

from modules.chat.conversation_manager import ConversationManager
from modules.chat.enums import ALLOWED_ATTACHEMENTS, AttachmentType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from modules.retrieval.service import RetrievalService
    from shared.llm.client import LLMClient
    from db.relational.models.user import User
    from db.relational.models.conversation import Conversation

logger = logging.getLogger(__name__)

@dataclass
class ValidatedAttachment:
    file: BinaryIO
    name: str
    type: AttachmentType
    size: int



async def validate_attachments(files: list[UploadFile]) -> list[ValidatedAttachment]:
    max_bytes = settings.chat.max_attachment_size_in_mbs * 1024 * 1024
    validated_attachments = []

    for file in files:

        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.MISSING_FILENAME
            )

        try:
            if not file.size:
                await asyncio.to_thread(file.file.seek, 0, os.SEEK_END)
                size = await asyncio.to_thread(file.file.tell)
                await asyncio.to_thread(file.file.seek, 0)
            else:
                size = file.size

            if size > max_bytes:
                logger.error("File too large — %s: %d bytes", file.filename, size)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.FILE_TOO_LARGE
                )

            head = await file.read(2048)
            await file.seek(0)
            type = magic.from_buffer(head, mime=True)

            if type not in ALLOWED_ATTACHEMENTS:
                logger.warning("Invalid file type — %s: %s", file.filename, type)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ErrorMessages.INVALID_TYPE
                )

        except HTTPException:
            raise  # let validation errors propagate as-is

        except Exception as e:
            logger.error("File validation failed — %s: %s", file.filename, e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorMessages.CORRUPTED_FILE
            )
        
        validated_attachments.append(ValidatedAttachment(
            file=file.file,
            name=file.filename,
            type=AttachmentType(type),
            size=size,
        ))

    return validated_attachments



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
        file_processor=AttachmentProcessor(llm_client, settings.chat),
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