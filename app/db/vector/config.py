from enum import Enum

from pydantic import BaseModel, model_validator


class VectorDBRepository(str, Enum):
    QDRANT = "qdrant"
    PGVECTOR = "pgvector"


class QdrantSettings(BaseModel):
    url: str
    collection_name: str = "uni_rag_chunks"
    api_key: str | None = None
    prefer_grpc: bool = False
    timeout: int = 10

 
class PgVectorSettings(BaseModel):
    sync_url: str
    async_url: str
    table_name: str = "uni_rag_chunks"
    pool_size: int = 10
    max_overflow: int = 20


class VectorDBSettings(BaseModel):
    provider: VectorDBRepository = VectorDBRepository.QDRANT

    qdrant: QdrantSettings | None = None
    pgvector: PgVectorSettings | None = None

    @model_validator(mode="after")
    def validate_provider_config(self):
        if self.provider == VectorDBRepository.QDRANT and self.qdrant is None:
            raise ValueError("Qdrant configuration is required")

        if self.provider == VectorDBRepository.PGVECTOR and self.pgvector is None:
            raise ValueError("PgVector configuration is required")

        return self
 