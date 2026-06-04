from __future__ import annotations
from typing import TYPE_CHECKING


from core.config import settings

from modules.ingestion.service import IngestionService


from db.relational.repositories.document_repository import SyncDocumentRepository
from db.relational.repositories.chunk_repository import SyncChunkRepository
from shared.embedder import Embedder
from db.vector.factory import get_sync_vector_repo
from shared.llm.dependencies import get_llm_client

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get_sync_ingestion_service(
        db: Session,
) -> IngestionService:
    return IngestionService(
        document_repo=SyncDocumentRepository(db),
        chunk_repo=SyncChunkRepository(db),
        embedder=Embedder(settings.embedding),
        vector_repo=get_sync_vector_repo(),
        llm_client=get_llm_client()
    )
