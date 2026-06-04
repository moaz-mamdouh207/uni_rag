from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Text,
    Integer,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase,  mapped_column, sessionmaker

from db.vector.base import AsyncVectorDBRepository, SyncVectorDBRepository
from db.vector.config import PgVectorSettings
from db.vector.schemas import SearchResult

if TYPE_CHECKING:
    from db.vector.schemas import VectorMetadata, SearchFilter


# ---------------------------------------------------------------------------
# ORM model
# ---------------------------------------------------------------------------

class _PgBase(DeclarativeBase):
    pass

def _build_model(table_name: str, dims: int) -> type:
    
    class VectorChunk(_PgBase):
        __allow_unmapped__ = True
        __tablename__ = table_name
        __table_args__ = (
            {"extend_existing": True},
        )

        id = mapped_column(Text, primary_key=True)
        user_id = mapped_column(Text, nullable=False) #moaz add index
        course_id = mapped_column(Text, nullable=False)
        document_id = mapped_column(Text, nullable=False)
        content = mapped_column(Text, nullable=False)
        index = mapped_column(Integer, nullable=False)
        starting_page = mapped_column(Integer, nullable=True)
        end_page = mapped_column(Integer, nullable=True)
        embedding = mapped_column(Vector(dims), nullable=False) #moaz: being set later and it cause hnsw to fail because it's more than 2000

    return VectorChunk


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_where_clauses(model: type, filters: SearchFilter) -> list:
    """Returns SQLAlchemy WHERE conditions for user/course/document filtering."""
    conditions = [
        model.user_id == str(filters.user_id),
        model.course_id == str(filters.course_id),
    ]
    if filters.documents_ids is not None:
        conditions.append(
            model.document_id.in_([str(d) for d in filters.documents_ids])
        )
    return conditions


# ---------------------------------------------------------------------------
# Sync provider  →  Celery
# ---------------------------------------------------------------------------

class PgVectorSyncProvider(SyncVectorDBRepository):
    """
    Synchronous pgvector provider for use in Celery tasks.

    Expects the pgvector extension and the target table to already exist
    (managed by Alembic migrations or ensure_collection on the async side).
    """

    def __init__(self, settings: PgVectorSettings, dims: int) -> None:
        self._settings = settings
        self._dims = dims
        self._model = _build_model(settings.table_name, dims)

        self._engine = create_engine(
            settings.sync_url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )

    # ------------------------------------------------------------------
    # SyncVectorDBRepository interface
    # ------------------------------------------------------------------

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

        rows = [
            {
                "id": str(uid),
                "user_id": str(meta.user_id),
                "course_id": str(meta.course_id),
                "document_id": str(meta.document_id),
                "content": meta.content,
                "index": meta.index,
                "starting_page": meta.starting_page,
                "end_page": meta.end_page,
                "embedding": vec,
            }
            for uid, vec, meta in zip(ids, vectors, metadatas)
        ]

        stmt = pg_insert(self._model).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "user_id": stmt.excluded.user_id,
                "course_id": stmt.excluded.course_id,
                "document_id": stmt.excluded.document_id,
                "content": stmt.excluded.content,
                "index": stmt.excluded.index,
                "starting_page": stmt.excluded.starting_page,
                "end_page": stmt.excluded.end_page,
                "embedding": stmt.excluded.embedding,
            },
        )

        with self._session_factory() as session:
            session.execute(stmt)
            session.commit()

    def scroll(
        self,
        limit: int = 10,
        with_payload: bool = True,
        with_vectors: bool = False,
    ) -> list[SearchResult]:
        from sqlalchemy import func
        with self._session_factory() as session:
            stmt = select(self._model).order_by(func.random()).limit(limit)
            rows = session.scalars(stmt).all()

        return [
            SearchResult(
                content=chunk.content,
                score=1.0,
                document_id=chunk.document_id,
                index=chunk.index,
                chunk_id=chunk.id,
            )
            for chunk in rows
        ]

# ---------------------------------------------------------------------------
# Async provider  →  FastAPI
# ---------------------------------------------------------------------------

class PgVectorAsyncProvider(AsyncVectorDBRepository):
    """
    Asynchronous pgvector provider for use in FastAPI routes.
    """

    def __init__(self, settings: PgVectorSettings, dims: int) -> None:
        self._settings = settings
        self._dims = dims
        self._model = _build_model(settings.table_name, dims)

        self._engine = create_async_engine(
            settings.async_url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    # ------------------------------------------------------------------
    # AsyncVectorDBRepository interface
    # ------------------------------------------------------------------

    async def ensure_collection(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
            await conn.run_sync(lambda sync_conn: _PgBase.metadata.create_all(sync_conn, checkfirst=True))

    async def search(
        self,
        filters: SearchFilter,
        query_vector: list[float],
        top_k: int,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        Cosine-similarity ANN search with hard user + course filters.

        pgvector's <=> operator computes cosine *distance* (0 = identical,
        2 = opposite), so score = 1 - distance.
        """
        model = self._model
        distance_expr = model.embedding.cosine_distance(query_vector).label("distance")

        conditions = _build_where_clauses(model, filters)

        stmt = (
            select(model, distance_expr)
            .where(*conditions)
            .order_by(distance_expr)
            .limit(top_k)
        )

        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()

        results: list[SearchResult] = []
        for chunk, distance in rows:
            score = 1.0 - float(distance)
            if score < score_threshold:
                continue
            results.append(
                SearchResult(
                    content=chunk.content,
                    score=score,
                    document_id=chunk.document_id,
                    index=chunk.index,
                    chunk_id=chunk.id,
                )
            )

        return results