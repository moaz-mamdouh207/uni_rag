from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, status, UploadFile


from db.relational.models.user import User
from db.relational.models.course import Course
from db.relational.models.document import Document

from modules.auth.dependencies import get_current_user
from modules.knowledge.dependencies import (
    get_current_course, 
    get_course_service, 
    get_current_document,
    get_document_service,
    validate_knowledge_files,
    validate_temp_files
)

from modules.knowledge.schemas import (
    CourseMetadata,
    DocumentMetadata,
    UploadTaskInfo
)

from db.relational.schemas import CourseCreate, CourseUpdate, DocumentUpdate


if TYPE_CHECKING:
    from modules.knowledge.course_service import CourseService
    from modules.knowledge.document_service import DocumentService

    
knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# course endpoints

@knowledge_router.post(
    "/courses",
    summary="create a new course",
    response_model=CourseMetadata,
    status_code=status.HTTP_201_CREATED
)
async def add_course(
    data: CourseCreate, 
    user: User = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service)
) -> CourseMetadata:
    response = await course_service.add_course(
        user_id=user.id, 
        data=data
    )
    return response


@knowledge_router.get(
    "/courses",
    summary="list all courses for the current user",
    response_model=list[CourseMetadata],
    status_code=status.HTTP_200_OK
)
async def list_courses(
    user: User = Depends(get_current_user),
    course_service: CourseService = Depends(get_course_service)
) -> list[CourseMetadata]:
    response = await course_service.list_courses(
        user_id=user.id
    )
    return response


@knowledge_router.patch(
    "/courses/{course_id}",
    summary="update course metadata",
    response_model=CourseMetadata,
    status_code=status.HTTP_200_OK
)
async def update_course(
    data: CourseUpdate, 
    course: Course = Depends(get_current_course),
    course_service: CourseService = Depends(get_course_service)
) -> CourseMetadata:
    response = await course_service.update_course(
        course=course,
        data=data
    )
    return response
    

@knowledge_router.delete(
    "/courses/{course_id}",
    summary="delete course (cascades to documents)",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_course(
    course: Course = Depends(get_current_course),
    course_service: CourseService = Depends(get_course_service)
) -> None:
    response = await course_service.delete_course(
        course=course
    )
    return response
    

 
# document endpoints

@knowledge_router.post(
    "/courses/{course_id}/documents",
    summary="upload documents to a course",
    response_model=list[UploadTaskInfo],
    status_code=status.HTTP_201_CREATED
)
async def upload_documents(
    files: list[UploadFile],
    course: Course = Depends(get_current_course),
    document_service: DocumentService = Depends(get_document_service)
) -> list[UploadTaskInfo]:
    validated_files = await validate_knowledge_files(files)
    response = await document_service.upload_dcouments(
        files=validated_files,
        course=course
    )
    return response


@knowledge_router.get(
    "/courses/{course_id}/documents",
    summary="list documents for a course",
    response_model=list[DocumentMetadata],
    status_code=status.HTTP_200_OK
)
async def list_documents(
    course: Course = Depends(get_current_course),
    document_service: DocumentService = Depends(get_document_service)
) -> list[DocumentMetadata]:
    response = await document_service.list_documents(
        course_id=course.id
    )
    return response


@knowledge_router.patch(
    "/courses/{course_id}/documents/{document_id}",
    summary="update document metadata",
    response_model=DocumentMetadata,
    status_code=status.HTTP_200_OK
)
async def update_document(
    data: DocumentUpdate,
    document: Document = Depends(get_current_document),
    document_service: DocumentService = Depends(get_document_service)
) -> DocumentMetadata:
    response = await document_service.update_document(
        data=data,
        document=document
    )
    return response


@knowledge_router.delete(
    "/courses/{course_id}/documents/{document_id}",
    summary="delete a document of a course",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_document(
    document: Document = Depends(get_current_document),
    document_service: DocumentService = Depends(get_document_service)
) -> None:
    response = await document_service.delete_document(
        document=document
    )
    return response


@knowledge_router.post(
    "/courses/temp_documents",
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
