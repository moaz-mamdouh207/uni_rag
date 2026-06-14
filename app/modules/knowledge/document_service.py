from __future__ import annotations
from uuid import UUID
from typing import TYPE_CHECKING


from modules.knowledge.schemas import  DocumentMetadata, UploadTaskInfo
from modules.knowledge.utils.asset import save_file_to_disk
from modules.knowledge.utils.manifest import register_manifest
from shared.enums import FileType
from db.relational.constants import DocumentStatus
from modules.ingestion.tasks import run_ingestion_pipeline
from db.relational.schemas import DocumentCreate
from modules.knowledge.schemas import PageRangeRequest, PageImagesResponse, PageImageItem

if TYPE_CHECKING:
    from db.relational.repositories.document_repository import AsyncDocumentRepository
    from db.relational.models.course import Course
    from db.relational.models.document import Document
    from db.relational.schemas import DocumentUpdate
    from modules.knowledge.dependencies import ValidatedFile


class DocumentService:
    def __init__(self, document_repository: AsyncDocumentRepository):
        self.document_repo = document_repository

    async def upload_dcouments(
        self, 
        course: Course, 
        files: list[ValidatedFile]
    ) -> list[UploadTaskInfo]:
        
        tasks = []

        for file in files:
            course_dir, file_path, stored_file_name, file_hash = await save_file_to_disk(
                course=course,
                original_file_name=file.original_name, 
                file=file.file
            )

            register_manifest(
                course_dir_path=course_dir,
                file_hash=file_hash,
                original_file_name=file.original_name,
                stored_file_name=stored_file_name,
            )

            document_create = DocumentCreate(
                original_name=file.original_name,
                stored_name=stored_file_name,
                type=FileType(file.type),
                file_path=str(file_path),
                status=DocumentStatus.UPLOADED
            )

            document = await self.add_document(
                data=document_create, 
                course_id=course.id
            )

            task = run_ingestion_pipeline(
                user_id=course.user_id,
                course_id=course.id,
                document_id=document.id
            )

            task = UploadTaskInfo(
                id=document.id,
                name=document.name,
                task_id=task.id
            )
            
            tasks.append(task)

        return tasks
    

    async def add_document(self, data: DocumentCreate, course_id: UUID) -> DocumentMetadata:
        document = await self.document_repo.add(
            data=data,
            course_id=course_id
        )
        return DocumentMetadata(
            id=document.id,
            name=document.original_name
        )


    async def list_documents(self, course_id: UUID) -> list[DocumentMetadata]:
        documents = await self.document_repo.get_all_by_course(course_id=course_id)
        return [DocumentMetadata(
            id=d.id,
            name=d.original_name
        ) for d in documents]


    async def update_document(self, data: DocumentUpdate, document: Document) -> DocumentMetadata:
        document = await self.document_repo.update(
            data=data,
            document=document
        )
        return DocumentMetadata(
            id=document.id,
            name=document.original_name
        )


    async def delete_document(self, document: Document) -> None:
        raise NotImplementedError() #moaz: need to fire an event
    
    
    def render_page_range(
        self,
        document: Document,
        start_page: int,
        end_page: int
    ) -> PageImagesResponse:
        import fitz
        import base64

        path = document.file_path

        pdf = fitz.open(path)
        total_pages = pdf.page_count

        if start_page > total_pages or end_page > total_pages:
            raise ValueError(f"Page range exceeds document length ({total_pages} pages)")
        if end_page < start_page:
            raise ValueError("end_page must be greater than or equal to start_page")

        items = []
        for page_num in range(start_page, end_page + 1):
            page = pdf[page_num - 1]  # convert to 0-indexed
            pixmap = page.get_pixmap(dpi=150)
            image_bytes = pixmap.tobytes("png")
            encoded = base64.b64encode(image_bytes).decode("utf-8")
            items.append(PageImageItem(page_number=page_num, image=encoded))

        pdf.close()

        return PageImagesResponse(pages=items)