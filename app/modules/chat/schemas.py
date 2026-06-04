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
    files: list[UUID] | None = Field(..., description="List of temp file IDs to include in the context")
    stream: bool = Field(default=False, description="Whether to stream the LLM response (reserved for future use)")


class ChatResponse(BaseModel):
    prompt: str
    answer: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str

    model_config = {
        "from_attributes": True
    }

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
    text:           str            # verbatim question/problem text from the file
    source_file_id: UUID | None    # None only on fallback plan
    context_hint:   str | None     # short topic label, e.g. "calculus", "MCQ"
 
 
class Plan(BaseModel):
    """The planner's full decision for a single chat turn."""
    queries:     list[ExtractedQuery]
    user_intent: str        # one-sentence description for PromptBuilder framing
    scope:       PlanScope