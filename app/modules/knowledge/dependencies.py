from __future__ import annotations
from typing import BinaryIO, TYPE_CHECKING
import os
import magic
import logging
import asyncio
from dataclasses import dataclass
from uuid import UUID


from fastapi import UploadFile, HTTPException, status, Depends


from core.config import settings
from shared.enums import FileType, ALLOWED_KNOWLEDGE

from shared.constants import ErrorMessages
from modules.knowledge.constants import UploadErrorMessages

from modules.knowledge.course_service import CourseService
from modules.knowledge.document_service import DocumentService

from db.relational.session import get_async_db
from modules.auth.dependencies import get_current_user

from db.relational.repositories.course_repository import AsyncCourseRepository
from db.relational.repositories.document_repository import AsyncDocumentRepository


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from db.relational.models.user import User
    from db.relational.models.course import Course
    from db.relational.models.document import Document


logger = logging.getLogger(__name__)

@dataclass
class ValidatedFile:
    file: BinaryIO
    original_name: str
    type: str
    size: int


async def validate_knowledge_files(files: list[UploadFile]) -> list[ValidatedFile]:
    document_settings = settings.document
    max_bytes = document_settings.max_document_size_in_mbs * 1024 * 1024
    validated_files = []

    for file in files:

        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=UploadErrorMessages.MISSING_FILENAME
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
                    detail=UploadErrorMessages.FILE_TOO_LARGE
                )

            head = await file.read(2048)
            await file.seek(0)
            type = magic.from_buffer(head, mime=True)

            if type not in ALLOWED_KNOWLEDGE:
                logger.warning("Invalid file type — %s: %s", file.filename, type)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=UploadErrorMessages.INVALID_TYPE
                )

        except HTTPException:
            raise  # let validation errors propagate as-is

        except Exception as e:
            logger.error("File validation failed — %s: %s", file.filename, e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=UploadErrorMessages.CORRUPTED_FILE
            )
        
        validated_files.append(ValidatedFile(
            file=file.file,
            original_name=file.filename,
            type=type,
            size=size,
        ))

    return validated_files


async def validate_temp_files(files: list[UploadFile]) -> list[ValidatedFile]:
    document_settings = settings.document
    max_bytes = document_settings.max_document_size_in_mbs * 1024 * 1024
    validated_files = []

    for file in files:

        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=UploadErrorMessages.MISSING_FILENAME
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
                    detail=UploadErrorMessages.FILE_TOO_LARGE
                )

            head = await file.read(2048)
            await file.seek(0)
            type = magic.from_buffer(head, mime=True)

            if type not in {item.value for item in FileType}:
                logger.warning("Invalid file type — %s: %s", file.filename, type)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=UploadErrorMessages.INVALID_TYPE
                )

        except HTTPException:
            raise  # let validation errors propagate as-is

        except Exception as e:
            logger.error("File validation failed — %s: %s", file.filename, e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=UploadErrorMessages.CORRUPTED_FILE
            )
        
        validated_files.append(ValidatedFile(
            file=file.file,
            original_name=file.filename,
            type=type,
            size=size,
        ))

    return validated_files



def get_course_service(
        db: AsyncSession = Depends(get_async_db),
) -> CourseService:
    return CourseService(
        course_repository=AsyncCourseRepository(db),
    )


def get_document_service(
        db: AsyncSession = Depends(get_async_db),
) -> DocumentService:
    return DocumentService(
        document_repository=AsyncDocumentRepository(db)
    )



async def get_current_course(
    course_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
    )-> Course:
    course_repo = AsyncCourseRepository(db)
    course = await course_repo.get_by_id(course_id=course_id)
    if course.user_id != user.id:
        raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ErrorMessages.FORBIDDEN_ACCESS
                )
    return course


async def get_current_document(
    document_id: UUID,
    course: Course = Depends(get_current_course),
    db: AsyncSession = Depends(get_async_db)
    )-> Document:
    document_repo = AsyncDocumentRepository(db)
    document = await document_repo.get_by_id(document_id=document_id)
    if document.course_id != course.id:
        raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=ErrorMessages.FORBIDDEN_ACCESS
                )
    return document
