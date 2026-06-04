from __future__ import annotations
from typing import TYPE_CHECKING

from fastapi import Depends


from core.config import settings

from modules.retrieval.service import RetrievalService

from db.vector.factory import get_async_vector_repo

from modules.retrieval.reranker import Reranker
from shared.embedder import Embedder


if TYPE_CHECKING:
    from db.vector.base import AsyncVectorDBRepository


def get_retrieval_service(
    vector_repo: AsyncVectorDBRepository = Depends(get_async_vector_repo)
) -> RetrievalService:
    return RetrievalService(
        reranker=Reranker(),
        embedder=Embedder(settings.embedding),
        vector_repo=vector_repo
    )
