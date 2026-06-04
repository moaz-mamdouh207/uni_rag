from __future__ import annotations
from typing import Sequence, TYPE_CHECKING
from uuid import UUID


from sqlalchemy import select


from db.relational.exceptions import NotFoundError

from db.relational.models.course import Course


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from db.relational.schemas import CourseCreate, CourseUpdate


class AsyncCourseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def add(self, data: CourseCreate, user_id: UUID) -> Course:
        course = Course(
            name=data.name,
            user_id=user_id
        )
        self._session.add(course)
        await self._session.commit()
        await self._session.refresh(course)
        return course


    async def get_by_id(self, course_id: UUID) -> Course:
        course = await self._session.get(Course, course_id)
        if course is None:
            raise NotFoundError("Course", str(course_id))
        return course


    async def get_all_by_user(self, user_id: UUID) -> Sequence[Course]:
        result = await self._session.execute(
            select(Course).where(Course.user_id == user_id)
        )
        return result.scalars().all()


    async def update(self, data: CourseUpdate, course: Course) -> Course:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(course, field, value)
        await self._session.commit()
        await self._session.refresh(course)
        return course


    async def delete(self, course: Course) -> None:
        await self._session.delete(course)
        await self._session.commit()
