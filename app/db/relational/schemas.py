from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel
from db.relational.constants import DocumentStatus,ChunkType, MessageRole

from shared.enums import FileType

class TokenCreate(BaseModel):
    user_id: UUID
    token_hash: str
    expires_at: datetime
    revoked: bool = False

class TokenUpdate(BaseModel):
    expires_at: datetime | None = None
    revoked: bool | None = None
    
# ───────────────────────── User ─────────────────────────

class UserCreate(BaseModel):
    email: str
    full_name: str
    hashed_password: str


class UserUpdate(BaseModel):
    email: str | None = None
    full_name: str | None = None
    hashed_password: str | None = None


# ───────────────────────── Course ─────────────────────────

class CourseCreate(BaseModel):
    name: str

 
class CourseUpdate(BaseModel):
    name: str



# ───────────────────────── Document ─────────────────────────

class DocumentCreate(BaseModel):
    original_name: str
    stored_name: str
    type: FileType
    file_path: str
    status: DocumentStatus


class DocumentUpdate(BaseModel):
    status: DocumentStatus | None = None
    status_message: str | None = None
    indexed_at: datetime | None  = None
    chunks_count: int | None = None



# ───────────────────────── Chunk ─────────────────────────

class ChunkCreate(BaseModel):
    index: int
    starting_page: int | None = None
    end_page: int | None = None
    token_count: int | None = None
    content: str
    type: ChunkType | None = None


class ChunkUpdate(BaseModel):
    starting_page: int | None = None
    end_page: int | None = None
    token_count: int | None = None
    content: str | None = None



# ───────────────────────── Conversation ─────────────────────────
class ConversationMetadata(BaseModel):
    course_id: UUID
    documents_ids: list[UUID] | None = None


class ConversationCreate(BaseModel):
    name: str
    meta: ConversationMetadata


class ConversationUpdate(BaseModel):
    name: str



# ───────────────────────── Message ─────────────────────────
class MessageCreate(BaseModel):
    role: MessageRole
    content: str
    token_count: int | None = None
