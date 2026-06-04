from pydantic import BaseModel, Field

from db.vector.schemas import SearchResult

class RetrievalResponse(BaseModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    total: int
