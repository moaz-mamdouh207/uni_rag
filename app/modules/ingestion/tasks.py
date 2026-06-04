from __future__ import annotations
import logging
from uuid import UUID

from sqlalchemy.exc import OperationalError
from celery.result import AsyncResult

from celery_app import celery
from modules.ingestion.dependencies import get_sync_ingestion_service
from modules.ingestion.exceptions import IngestionError
from db.relational.session import get_sync_db
from modules.ingestion.schemas import TaskStatusResponse, TaskStatus
from db.vector.schemas import VectorMetadata



logger = logging.getLogger(__name__)


@celery.task(
    bind=True,
    name="ingestion.process",
    max_retries=3,
)
def process_task(
    self,
    user_id: UUID,
    course_id: UUID,
    document_id: UUID,
):
    logger.info("process_task started: file=%s", document_id)

    try:
        with get_sync_db() as session:
            service = get_sync_ingestion_service(db=session)

            ids, content, metadatas = service.process_file(
                user_id=user_id,
                course_id=course_id,
                document_id=document_id,
            )

            logger.info("process_task complete: file=%s", document_id)

            metadatas_dicts = [metadata.model_dump() for metadata in metadatas]
            return ids, content, metadatas_dicts
        
    except IngestionError as e:
        logger.warning("Ingestion error (attempt %s): %s", self.request.retries, e)
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except OperationalError as e:
        logger.warning("DB transient error (attempt %s): %s", self.request.retries, e)
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        logger.exception("Unrecoverable error — not retrying: %s", e)
        raise


@celery.task(
    bind=True,
    name="ingestion.index",
    max_retries=3,
)
def index_task(
    self,
    chunks: tuple[list[UUID], list[str], list[dict]]
):
    ids, contents, metadatas = chunks
    logger.info("process_task started: course=%s", metadatas[0].get("course_id") if metadatas else "unknown")

    try:
        with get_sync_db() as session:
            service = get_sync_ingestion_service(db=session)

            response = service.index_file(
                ids=ids,
                contents=contents,
                metadatas=[VectorMetadata(**metadata) for metadata in metadatas]
            )

            logger.info("ingest_task complete: chunks=%d", response)

            return response
        
    except IngestionError as e:
        logger.warning("Ingestion error (attempt %s): %s", self.request.retries, e)
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except OperationalError as e:
        logger.warning("DB transient error (attempt %s): %s", self.request.retries, e)
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        logger.exception("Unrecoverable error — not retrying: %s", e)
        raise


def run_ingestion_pipeline(
    user_id: UUID,
    course_id: UUID,
    document_id: UUID,
):
    pipeline= (
        process_task.s(user_id=user_id, course_id=course_id, document_id=document_id) | 
        index_task.s()
    )
    return pipeline.apply_async()


def get_task_status(task_id: str) -> TaskStatusResponse:
    result = AsyncResult(task_id, app=celery)
    
    status = TaskStatus(result.status)
    
    task_result = None
    error = None
    
    if result.successful():
        task_result = {"result": str(result.result)}
    elif result.failed():
        error = str(result.result)
    
    return TaskStatusResponse(
        task_id=task_id,
        status=status,
        result=task_result,
        error=error
    )