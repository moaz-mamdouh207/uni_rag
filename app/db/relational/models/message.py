from __future__ import annotations
from typing import TYPE_CHECKING
import uuid

from pydantic import ConfigDict
from sqlalchemy import Enum, ForeignKey, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.relational.constants import MessageRole
from db.relational.models.base import Base, GUID

if TYPE_CHECKING:
    from db.relational.models.conversation import Conversation
    
class Message(Base):
    __tablename__ = "message"
    __pydantic_config__ = ConfigDict(from_attributes=True)
    
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, native_enum=False), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_message_conversation_id", "conversation_id"),
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id!r} role={self.role} conv={self.conversation_id!r}>"