from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID
import random

from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, VectorParams, Distance
from qdrant_client.http import models as qmodels

from db.vector.base import AsyncVectorDBRepository, SyncVectorDBRepository

from db.vector.config import QdrantSettings
from db.vector.schemas import SearchResult

if TYPE_CHECKING:
    from db.vector.schemas import VectorMetadata, SearchFilter
    from qdrant_client.models import Condition

# ---------------------------------------------------------------------------
# Sync provider  →  Celery
# ---------------------------------------------------------------------------

class QdrantSyncProvider(SyncVectorDBRepository):
    def __init__(self, settings: QdrantSettings, dims: int) -> None:
        self._collection = settings.collection_name
        self._dims = dims
        self._client = QdrantClient(
            url=str(settings.url),
            api_key=settings.api_key,
            prefer_grpc=settings.prefer_grpc,
            timeout=settings.timeout,
        )

    def upsert(
        self,
        ids: list[UUID],
        vectors: list[list[float]],
        metadatas: list[VectorMetadata],
    ) -> None:
        if not (len(ids) == len(vectors) == len(metadatas)):
            raise ValueError(
                f"ids, vectors and metadatas must be the same length, "
                f"got {len(ids)}, {len(vectors)}, {len(metadatas)}"
            )
        points = [
            qmodels.PointStruct(id=p_id, vector=vec, payload=meta.model_dump())
            for p_id, vec, meta in zip(ids, vectors, metadatas)
        ]
        self._client.upsert(collection_name=self._collection, points=points, wait=True)


    def scroll(
        self, 
        user_id: UUID,
        course_id: UUID,
        limit: int = 10, 
        with_payload: bool = True, 
        with_vectors: bool = False
    ) -> list[SearchResult]:
        """
        Scrolls through the collection with hard user + course filters 
        and returns a chunk of records.
        """
        candidate_pool_size = max(100, limit * 3)
        
        # Define Qdrant filter for metadata
        # Adjust "user_id" or "metadata.user_id" depending on how your payload is structured
        qdrant_filter = Filter(
            must=[
                FieldCondition(key="user_id", match=MatchValue(value=str(user_id))),
                FieldCondition(key="course_id", match=MatchValue(value=str(course_id)))
            ]
        )
        
        records, _ = self._client.scroll(
            collection_name=self._collection,
            scroll_filter=qdrant_filter,  # Inject the filter here
            limit=candidate_pool_size,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )
        
        if not records:
            return []

        random.shuffle(records)
        records = records[:limit]

        return [
            SearchResult(
                content=record.payload.get("content"), # type: ignore
                score=1.0,
                document_id=record.payload.get("document_id"), # type: ignore
                index=record.payload.get("index"), # type: ignore
                chunk_id=str(record.id),
            )
            for record in records
        ]

# ---------------------------------------------------------------------------
# Async provider  →  FastAPI
# ---------------------------------------------------------------------------

class QdrantAsyncProvider(AsyncVectorDBRepository):
    def __init__(self, settings: QdrantSettings, dims: int) -> None:
        self._collection = settings.collection_name
        self._dims = dims
        self._client = AsyncQdrantClient(
            url=str(settings.url),
            api_key=settings.api_key,
            prefer_grpc=settings.prefer_grpc,
            timeout=settings.timeout,
        )

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._dims, distance=Distance.COSINE),
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="user_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="course_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )


    async def search(
        self,
        filters: SearchFilter,
        query_vector: list[float],
        top_k: int,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:

        must_conditions: list[Condition] = [
            FieldCondition(
                key="user_id",
                match=MatchValue(value=str(filters.user_id)),
            ),
            FieldCondition(
                key="course_id",
                match=MatchValue(value=str(filters.course_id)),
            ),
        ]

        if filters.documents_ids is not None:
            must_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=[str(doc_id) for doc_id in filters.documents_ids]),
                )
            )

        results = await self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=Filter(must=must_conditions), 
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        search_results: list[SearchResult] = []

        for point in results.points:
            payload = point.payload

            if payload is None:
                continue

            search_results.append(
                SearchResult(
                    content=payload["content"],
                    score=point.score,
                    document_id=payload["document_id"],
                    index=payload["index"],
                    chunk_id=str(point.id),
                )
            )

        return search_results
