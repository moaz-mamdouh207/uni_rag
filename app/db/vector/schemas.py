from pydantic import BaseModel, Field
from uuid import UUID

from db.relational.constants import ChunkType

class ChunkMetaData(BaseModel):
    user_id: UUID
    course_id: UUID
    document_id: UUID
    content: str
    index: int
    type: ChunkType
    starting_page: int
    end_page: int


class SearchFilter(BaseModel):
    user_id: UUID
    course_id: UUID
    documents_ids: list[UUID] | None
    type: ChunkType | None


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    rerank: bool = Field(default=False)


class SearchResult(BaseModel):
    content: str
    score: float
    document_id: str
    index: int
    chunk_id: str
