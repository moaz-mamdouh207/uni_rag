from __future__ import annotations
from typing import Sequence, TYPE_CHECKING
from uuid import UUID


from sqlalchemy import select

from db.relational.exceptions import NotFoundError

from db.relational.models.document import Document

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session
    from db.relational.schemas import DocumentCreate, DocumentUpdate


class AsyncDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

 
    async def add(self, data: DocumentCreate, course_id: UUID) -> Document:
        document = Document(**data.model_dump(), course_id=course_id)
        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)
        return document



    async def bulk_add(self, data: list[DocumentCreate], course_id: UUID) -> list[Document]:
        documents = [Document(
            **d.model_dump(),
            course_id=course_id
        ) for d in data]
        self._session.add_all(documents)
        await self._session.commit()
        for doc in documents:
            await self._session.refresh(doc)
        return documents


    async def get_all_by_course(self, course_id: UUID) -> Sequence[Document]:
        result = await self._session.execute(
            select(Document).where(Document.course_id == course_id)
        )
        return result.scalars().all()
    

    async def get_by_id(self, document_id: UUID) -> Document:
        document = await self._session.get(Document, document_id)
        if document is None:
            raise NotFoundError("document", str(document_id))
        return document


    async def update(self, data: DocumentUpdate, document: Document) -> Document:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(document, field, value)
        await self._session.commit()
        await self._session.refresh(document)
        return document

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
        await self._session.commit()



class SyncDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session


    def get_by_id(self, document_id: UUID) -> Document:
        document = self._session.get(Document, document_id)
        if document is None:
            raise NotFoundError("document", str(document_id))
        return document
    

    def update(self, data: DocumentUpdate, document: Document) -> Document:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(document, field, value)
        self._session.commit()
        self._session.refresh(document)
        return document
