from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from db.vector.schemas import SearchQuery, SearchResult, SearchFilter

from shared.embedder import Embedder



from modules.retrieval.schemas import RetrievalResponse

from modules.retrieval.reranker import Reranker

if TYPE_CHECKING:
    from db.vector.base import AsyncVectorDBRepository
    from db.relational.constants import ChunkType


class RetrievalService:
    def __init__(
        self, 
        reranker: Reranker,
        embedder: Embedder,
        vector_repo: AsyncVectorDBRepository,
    ):
        self._reranker = reranker
        self._embedder = embedder
        self._vector_repo = vector_repo

    async def retrieve(
        self,
        request: SearchQuery,
        user_id: UUID,
        course_id: UUID,
        documents_ids: list[UUID] | None = None,
        type: ChunkType | None = None
    ) -> RetrievalResponse:
        """
        Full retrieval pipeline for a single query.

        Steps:
          1. Embed the query via the embedder module.
          2. Run vector similarity search.
          3. Optionally rerank results.
          4. Return a structured RetrievalResponse.
        """
        # 1. Embed query
        query_vector = await self._embedder.embed_query(request.query)
        
        # 2. Vector search
        filters = SearchFilter(
            user_id=user_id,
            course_id=course_id,
            documents_ids=documents_ids,
            type=type
        )

        results: list[SearchResult] = await self._vector_repo.search(
            query_vector=query_vector,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            filters=filters
        )

        # 3. Optional rerank
        if request.rerank:
            results = await self._reranker.rerank(query=request.query, results=results)

        # 4. Response
        return RetrievalResponse(
            query=request.query,
            results=results,
            total=len(results),
        )
