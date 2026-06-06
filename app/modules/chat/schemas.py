from __future__ import annotations
from typing import TYPE_CHECKING, Sequence
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class ConversationMetadata(BaseModel):
    id: UUID
    name: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    files: list[UUID] | None = Field(
        default=None,
        description="List of temp file IDs to include in the context",
    )
    stream: bool = Field(default=False, description="Reserved for future streaming support")


class ChatResponse(BaseModel):
    answer: str
    sources: list[CitedSource] = Field(
        default_factory=list,
        description="Chunks cited by the agent, with document and page info",
    )
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class CitedSource(BaseModel):
    """A single retrieval chunk surfaced to the caller for citation display."""
    document_id: str
    chunk_index: int
    chunk_id: str
    score: float
    content_preview: str  # first 200 chars — enough for the UI to show a snippet


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str

    model_config = {"from_attributes": True}


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: Sequence[MessageResponse]
    total: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FileType(str, Enum):
    PDF   = "pdf"
    IMAGE = "image"


class PlanScope(str, Enum):
    specific  = "specific"
    all       = "all"
    ambiguous = "ambiguous"


# ---------------------------------------------------------------------------
# FileProcessor output
# ---------------------------------------------------------------------------

class FileExtractionResult(BaseModel):
    """One VLM extraction per attached file."""
    file_id:          UUID
    file_type:        FileType
    markdown_content: str  # raw structured markdown from VLM; may be NO_ITEMS_FOUND


# ---------------------------------------------------------------------------
# Planner output
# ---------------------------------------------------------------------------

class ExtractedQuery(BaseModel):
    """One retrieval query derived from an extracted file item."""
    text:           str
    source_file_id: UUID | None = None
    context_hint:   str | None = None


class Plan(BaseModel):
    """The planner's full decision for a single chat turn."""
    queries:     list[ExtractedQuery]
    user_intent: str
    scope:       PlanScope