from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status, UploadFile
 

from db.relational.models.user import User
from db.relational.models.conversation import Conversation

from modules.auth.dependencies import get_current_user

from modules.chat.dependencies import (
    get_chat_service, 
    get_current_conv
)

from modules.chat.schemas import (
    Attachment,
    ConversationMetadata,
    ChatRequest, 
    ChatResponse, 
    MessageMetadata
)

from db.relational.schemas import ConversationCreate, ConversationUpdate

from modules.chat.dependencies import validate_attachments

if TYPE_CHECKING:
    from modules.chat.service import ChatService


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
    return await chat_service.list_conversations(
        user_id=user.id
    )


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
    return await chat_service.update_conversation(
        conv=conv,
        data=data
    )
    

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
    return await chat_service.delete_conversation(
        conv=conv
    )



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
    return await service.chat(
        conv=conv, 
        request=request
    )


@chat_router.post(
    "/conversations/{conversation_id}/messages/attachments",
    summary="upload temporary documents to be used in chat",
    response_model=list[Attachment],
    status_code=status.HTTP_201_CREATED
)
async def attach_documents(
    files: list[UploadFile],
    conv: Conversation = Depends(get_current_conv),
    service: ChatService = Depends(get_chat_service),
) -> list[Attachment]:
    validated_attachments = await validate_attachments(files)
    return await service.attach_documents(
        attachments=validated_attachments
    )

 
@chat_router.get(
    "/conversations/{conversation_id}/messages",
    summary="Fetch the full message history for a conversation",
    response_model=list[MessageMetadata],
    status_code=status.HTTP_200_OK,
)
async def get_history(
    conv: Conversation = Depends(get_current_conv),
    service: ChatService = Depends(get_chat_service),
) -> list[MessageMetadata]:
    return await service.list_messages(conv.id)
