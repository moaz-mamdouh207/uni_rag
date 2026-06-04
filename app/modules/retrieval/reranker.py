"""
Reranker — sorts an initial candidate list by relevance to the query.

MVP: score-based passthrough (no-op). Swap the `_rerank_scores` method
for a real cross-encoder (e.g. Cohere Rerank, ms-marco) without changing
any other module.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from db.vector.schemas import SearchResult


logger = logging.getLogger(__name__)


class Reranker:
    """
    Reranks a list of RetrievalResult objects given the original query.

    The base implementation is a no-op passthrough that preserves the
    vector-search ordering. Override `_rerank_scores` to plug in a real model.
    """

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """
        Rerank results and return them sorted by the new score, descending.

        Args:
            query:   The original user query string.
            results: Candidate chunks from the vector search stage.

        Returns:
            Re-sorted list of RetrievalResult with updated scores.
        """
        if not results:
            return results

        try:
            scores = await self._rerank_scores(query, results)
        except Exception as exc:
            logger.exception("Reranker failed; falling back to original order")

        reranked = [
            SearchResult(
                content=result.content,
                score=score,
                document_id=result.document_id,
                index=result.index,
                chunk_id=result.chunk_id
            )
            for result, score in zip(results, scores)
        ]
        reranked.sort(key=lambda r: r.score, reverse=True)
        logger.debug("Reranker reordered %d results", len(reranked))
        return reranked

    async def _rerank_scores(
        self,
        query: str,
        results: list[SearchResult],
    ) -> list[float]:
        """
        Compute a relevance score for each (query, chunk) pair.

        MVP: passthrough — returns the original vector similarity scores unchanged.
        Replace this method to integrate a cross-encoder without touching anything else.

        Example swap-in:
            import cohere
            co = cohere.Client(api_key)
            response = co.rerank(model="rerank-english-v3.0", query=query,
                                 documents=[r.text for r in results])
            return [hit.relevance_score for hit in response.results]
        """
        return [result.score for result in results]
