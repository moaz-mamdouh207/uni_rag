from __future__ import annotations
from typing import TYPE_CHECKING
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.relational.constants import DocumentStatus
from shared.enums import FileType
from db.relational.models.base import Base, GUID

if TYPE_CHECKING:
    from db.relational.models.chunk import Chunk
    from db.relational.models.course import Course
    
class Document(Base):
    __tablename__ = "document"

    course_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    original_name: Mapped[str] = mapped_column(String, nullable=False)
    stored_name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[FileType] = mapped_column(
        Enum(FileType, native_enum=False),
        nullable=False
    )
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    chunks_count: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False),
        nullable=False,
        default=DocumentStatus.UPLOADED,
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    course: Mapped["Course"] = relationship("Course", back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_document_course_id_status", "course_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id!r}>"