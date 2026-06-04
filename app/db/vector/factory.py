from functools import lru_cache

from db.vector.base import AsyncVectorDBRepository, SyncVectorDBRepository
from db.vector.config import VectorDBRepository as ProviderEnum

from core.config import settings, Settings

@lru_cache()
def _build_sync_provider(settings: Settings = settings) -> SyncVectorDBRepository:
    match settings.vector_db.provider:
        case ProviderEnum.QDRANT:
            from db.vector.providers.qdrant import QdrantSyncProvider
            return QdrantSyncProvider(settings.vector_db.qdrant, settings.embedding.dimension) # type: ignore
        case ProviderEnum.PGVECTOR:
            from db.vector.providers.pgvector import PgVectorSyncProvider
            return PgVectorSyncProvider(settings.vector_db.pgvector, settings.embedding.dimension) # type: ignore
        case _:
            raise ValueError(f"Unknown provider: {settings.vector_db.provider}")


@lru_cache()
def _build_async_provider(settings: Settings = settings) -> AsyncVectorDBRepository:
    match settings.vector_db.provider:
        case ProviderEnum.QDRANT:
            from db.vector.providers.qdrant import QdrantAsyncProvider
            return QdrantAsyncProvider(settings.vector_db.qdrant, settings.embedding.dimension) # type: ignore
        case ProviderEnum.PGVECTOR:
            from db.vector.providers.pgvector import PgVectorAsyncProvider
            return PgVectorAsyncProvider(settings.vector_db.pgvector, settings.embedding.dimension) # type: ignore
        case _:
            raise ValueError(f"Unknown provider: {settings.vector_db.provider}")


def get_sync_vector_repo() -> SyncVectorDBRepository:
    """Celery / sync entry point."""
    return _build_sync_provider() # type: ignore


def get_async_vector_repo() -> AsyncVectorDBRepository:
    """FastAPI Depends() entry point."""
    return _build_async_provider() # type: ignore