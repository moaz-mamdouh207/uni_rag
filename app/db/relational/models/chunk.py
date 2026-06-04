from __future__ import annotations
from typing import TYPE_CHECKING
import uuid

from  sqlalchemy import ForeignKey, Index, Integer, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.relational.constants import ChunkType

from db.relational.models.base import Base, GUID
 
if TYPE_CHECKING:
    from db.relational.models.document import Document

class Chunk(Base):
    __tablename__ = "chunk"

    document_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("document.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    starting_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[ChunkType] = mapped_column(
        Enum(ChunkType, native_enum=False),
        nullable=False,
        default=ChunkType.THEORY,
    )
    
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunk_document_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<Chunk id={self.id!r}>"