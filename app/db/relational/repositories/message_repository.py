from __future__ import annotations
from typing import Sequence, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from db.relational.models import Message


if TYPE_CHECKING:
    from db.relational.schemas import MessageCreate


class AsyncMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, data: MessageCreate, conversation_id: UUID) -> Message:
        msg = Message(**data.model_dump(), conversation_id=conversation_id)
        self._session.add(msg)
        await self._session.commit()
        await self._session.refresh(msg)
        return msg
    

    async def get_all_by_conversation(self, conversation_id: UUID) -> Sequence[Message]:
        result = await self._session.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
        )
        return result.scalars().all()