from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, status, UploadFile
 

from db.relational.models.user import User
from db.relational.models.conversation import Conversation

from modules.auth.dependencies import get_current_user

from modules.chat.agent.dependencies import (
    get_chat_service, 
    get_current_conv
)

from modules.chat.schemas import (
    ConversationMetadata,
    ChatRequest, 
    ChatResponse, 
    ConversationHistoryResponse
)

from db.relational.schemas import ConversationCreate, ConversationUpdate

from modules.knowledge.dependencies import get_document_service, validate_temp_files

if TYPE_CHECKING:
    from modules.chat.service import ChatService
    from modules.knowledge.document_service import DocumentService


chat_router = APIRouter(prefix="/chat", tags=["chat"])


@chat_router.post(
    "/conversations",
    summary="create a new conversation",
    response_model=ConversationMetadata,
    status_code=status.HTTP_201_CREATED
)
async def add_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
)-> ConversationMetadata:
    response = await chat_service.add_conversation(
        user_id=user.id,
        data=data
    )
    return response


@chat_router.get(
    "/conversations",
    summary="list all conversations for the current user",
    response_model=list[ConversationMetadata],
    status_code=status.HTTP_200_OK
)
async def list_conversations(
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ConversationMetadata]:
    response = await chat_service.list_conversations(
        user_id=user.id
    )
    return response


@chat_router.patch(
    "/conversations/{conversation_id}",
    summary="update conversation name",
    response_model=ConversationMetadata,
    status_code=status.HTTP_200_OK
)
async def update_conversation(
    data: ConversationUpdate,
    conv: Conversation = Depends(get_current_conv),
    chat_service: ChatService = Depends(get_chat_service)
) -> ConversationMetadata:
    response = await chat_service.update_conversation(
        conv=conv,
        data=data
    )
    return response
    

@chat_router.delete(
    "/conversations/{conversation_id}",
    summary="delete conversation",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_conversation(
    conv: Conversation = Depends(get_current_conv),
    chat_service: ChatService = Depends(get_chat_service)
) -> None:
    response = await chat_service.delete_conversation(
        conv=conv
    )
    return response


@chat_router.post(
    "/conversations/{conversation_id}/messages",
    summary="Send a message and receive a RAG-grounded answer",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def send_message(
    request: ChatRequest,
    conv: Conversation = Depends(get_current_conv),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    response = await service.chat(
        conv=conv, 
        request=request
    )
    return response


@chat_router.post(
    "/conversations/{conversation_id}/messages/attachments",
    summary="upload temporary documents to be used in chat",
    response_model=list[UUID],
    status_code=status.HTTP_201_CREATED
)
async def upload_temp_documents(
    files: list[UploadFile],
    user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service)
) -> list[UUID]:
    validated_files = await validate_temp_files(files)
    response = await document_service.upload_temp_documents(
        files=validated_files
    )
    return response


@chat_router.get(
    "/conversations/{conversation_id}/history",
    summary="Fetch the full message history for a conversation",
    response_model=ConversationHistoryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_history(
    conv: Conversation = Depends(get_current_conv),
    service: ChatService = Depends(get_chat_service),
) -> ConversationHistoryResponse:
    return await service.get_history(conv.id)
