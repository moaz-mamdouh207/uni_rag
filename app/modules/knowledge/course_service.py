from __future__ import annotations
from uuid import UUID
from typing import TYPE_CHECKING


from modules.knowledge.schemas import CourseMetadata


if TYPE_CHECKING:
    from db.relational.repositories.course_repository import AsyncCourseRepository
    from db.relational.models.course import Course
    from db.relational.schemas import CourseCreate, CourseUpdate


class CourseService:
    def __init__(self, course_repository: AsyncCourseRepository):
        self._course_repo = course_repository

    async def add_course(self, data: CourseCreate, user_id: UUID) -> CourseMetadata:
        course = await self._course_repo.add(
            data=data,
            user_id=user_id
        )
        return CourseMetadata(
            id=course.id,
            name=course.name
        )

    async def list_courses(self, user_id: UUID) -> list[CourseMetadata]:
        courses = await self._course_repo.get_all_by_user(user_id=user_id)
        return [CourseMetadata(
            id=c.id,
            name=c.name
        ) for c in courses]

    async def update_course(self, data: CourseUpdate, course: Course) -> CourseMetadata:
        course = await self._course_repo.update(
            data=data,
            course=course
        )
        return CourseMetadata(
            id=course.id,
            name=course.name
        )

    async def delete_course(self, course: Course) -> None:
        raise NotImplementedError() #moaz: need to fire an event
    