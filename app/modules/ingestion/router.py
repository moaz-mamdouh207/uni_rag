from fastapi import APIRouter, Depends
from modules.auth.dependencies import get_current_user
from modules.ingestion.tasks import get_task_status
from modules.ingestion.schemas import TaskStatusResponse

ingestion_router = APIRouter(prefix="/tasks", tags=["tasks"])


@ingestion_router.get(
    "/{task_id}",
    summary="Get the status of an ingestion task",
    response_model=TaskStatusResponse,
)
async def task_status(
    task_id: str,
    _: object = Depends(get_current_user),  # require auth
) -> TaskStatusResponse:
    return get_task_status(task_id)