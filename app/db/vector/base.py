from __future__ import annotations
from typing import TYPE_CHECKING
from abc import ABC, abstractmethod
from uuid import UUID

if TYPE_CHECKING:
    from db.vector.schemas import VectorMetadata, SearchFilter, SearchResult


# ---------------------------------------------------------------------------
# Sync interface  →  Celery ingestion tasks
# ---------------------------------------------------------------------------

class SyncVectorDBRepository(ABC):
    """Sync-only interface — used exclusively in Celery tasks."""

    @abstractmethod
    def upsert(
        self,
        ids: list[UUID],
        vectors: list[list[float]],
        metadatas: list[VectorMetadata],
    ) -> None:
        """Insert or update a batch of vectors. Idempotent."""

    @abstractmethod
    def scroll(
        self,
        user_id: UUID,
        course_id: UUID,
        limit: int = 10, 
        with_payload: bool = True, 
        with_vectors: bool = False
    ) -> list[SearchResult]:
        """Scroll through the collection and return a chunk of records. 
        To simulate randomness efficiently, it attempts to skip to a random offset 
        before returning the next `limit` records. Returns both the records and the next offset for pagination."""


# ---------------------------------------------------------------------------
# Async interface  →  FastAPI retrieval endpoints
# ---------------------------------------------------------------------------

class AsyncVectorDBRepository(ABC):
    """Async-only interface — used exclusively in FastAPI routes."""

    @abstractmethod
    async def ensure_collection(self) -> None:
        """Create the collection / table if it doesn't exist."""

    @abstractmethod
    async def search(
        self,
        filters: SearchFilter,
        query_vector: list[float],
        top_k: int,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """ANN search with mandatory user + course hard filter."""