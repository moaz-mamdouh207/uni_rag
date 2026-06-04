from __future__ import annotations
from typing import Sequence, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.relational.exceptions import NotFoundError
from db.relational.models import Conversation

if TYPE_CHECKING:
    from db.relational.schemas import ConversationCreate, ConversationUpdate


class AsyncConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, data: ConversationCreate, user_id: UUID) -> Conversation:
        conv = Conversation(
            name=data.name,
            user_id=user_id,
            meta=data.meta
        )
        self._session.add(conv)
        await self._session.commit()
        await self._session.refresh(conv)
        return conv
    

    async def get_by_id(self, conversation_id: UUID) -> Conversation:
        conv = await self._session.get(Conversation, conversation_id)
        if conv is None:
            raise NotFoundError("conversation", str(conversation_id))
        return conv


    async def get_all_by_user(self, user_id: UUID) -> Sequence[Conversation]:
        result = await self._session.execute(
            select(Conversation).where(Conversation.user_id == user_id)
        )
        return result.scalars().all()


    async def update(self, data: ConversationUpdate, conversation: Conversation) -> Conversation:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(conversation, field, value)
        await self._session.commit()
        await self._session.refresh(conversation)
        return conversation
    
    
    async def delete(self, conversation: Conversation) -> None:
        await self._session.delete(conversation)
        await self._session.commit()
