from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.relational.models import User

from db.relational.exceptions import NotFoundError


if TYPE_CHECKING:
    from db.relational.schemas import UserCreate, UserUpdate

    
class AsyncUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user


    async def get_by_id(self, user_id: UUID) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            raise NotFoundError(entity="user", id=str(user_id))
        return user
   
    
    async def get_by_email(self, email: str) -> User | None:
        return await self._session.scalar(
            select(User).where(User.email == email)
        )


    async def update(self, data: UserUpdate, user: User) -> User:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await self._session.commit()
        await self._session.refresh(user)
        return user


    async def delete(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.commit()