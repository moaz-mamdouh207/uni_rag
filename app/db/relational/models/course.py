from __future__ import annotations
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.relational.models.base import Base, GUID

if TYPE_CHECKING:
    from db.relational.models.user import User
    from db.relational.models.document import Document
 
class Course(Base):
    __tablename__ = "course"

    name: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="courses")
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="course", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uq_course_name_user_id"),
    )

    def __repr__(self) -> str:
        return f"<Course id={self.id!r}>"