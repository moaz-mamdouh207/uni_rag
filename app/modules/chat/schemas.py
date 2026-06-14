from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel, Field

from PIL.Image import Image

from modules.chat.enums import AttachmentType

# ── Requests ──────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    attachments: list[Attachment] | None 
    stream: bool = Field(default=False, description="Reserved for future support")



# ── Responses ─────────────────────────────────────────────────────────────────
class ConversationMetadata(BaseModel):
    "The metadata exposed to the front end"
    id: UUID
    name: str


class MessageMetadata(BaseModel):
    "The metadata exposed to the front end"
    role: str
    content: str

 
class Attachment(BaseModel):
    "The metadata exposed to the front end for attached files"
    id: UUID
    type: AttachmentType


class ChatResponse(BaseModel):
    "The response model for the chat endpoint"
    answer: str
    sources: list[CitedSource] = Field(
        default_factory=list,
        description="Chunks cited by the agent, with document and page info",
    )


class CitedSource(BaseModel):
    index: str
    reason: str
    document_id: UUID
    starting_page: int
    end_page: int


class CitationMetaData(BaseModel):
    document_id: UUID
    starting_page: int
    end_page: int









class CitedSources(BaseModel):
    "A single retrieval chunk surfaced to the caller for citation display."
    inline_index: int                  # the [N] number used inline in the answer text
    chunk_id: str
    document_id: str
    chunk_type: str | None = None      # "theory" or "solved_question"
    score: float
    full_content: str                  # complete chunk text for hover display
    content_preview: str               # first 200 chars for quick display
    starting_page: int | None = None
    end_page: int | None = None
