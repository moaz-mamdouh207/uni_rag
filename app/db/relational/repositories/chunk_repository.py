from __future__ import annotations
from uuid import UUID
from typing import TYPE_CHECKING

from db.relational.models.chunk import Chunk


if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from db.relational.schemas import ChunkCreate


class SyncChunkRepository:

    def __init__(self, session: Session) -> None:
        self._session = session


    def add(self, data: ChunkCreate, document_id: UUID) -> Chunk:
        chunk = Chunk(**data.model_dump(), document_id=document_id)
        self._session.add(chunk)
        self._session.commit()
        self._session.refresh(chunk)
        return chunk


    def bulk_add(self, data: list[ChunkCreate], document_id: UUID) -> list[Chunk]:
        chunks = [Chunk(
            **d.model_dump(),
            document_id=document_id,
        ) for d in data]
        self._session.add_all(chunks)
        self._session.commit()
        for chunk in chunks:
            self._session.refresh(chunk)
        return chunks
