from enum import StrEnum
from pydantic import BaseModel, Field, model_validator

class TaskStatus(StrEnum):
    PENDING  = "PENDING"
    STARTED  = "STARTED"
    SUCCESS  = "SUCCESS"
    FAILURE  = "FAILURE"
    RETRY    = "RETRY"
    REVOKED  = "REVOKED"

class ProcessTaskInfo(BaseModel):
    original_file_name: str
    task_id: str
    status: TaskStatus = TaskStatus.PENDING


class BatchProcessResponse(BaseModel):
    message: str = "Files processing queued."
    tasks: list[ProcessTaskInfo]
    total: int = Field(default=0)

    @model_validator(mode="after")
    def set_total(self) -> "BatchProcessResponse":
        self.total = len(self.tasks)
        return self
    
class ProcessFileResponse(BaseModel):
    message: str = "File processed successfully"
    course_name: str
    original_file_name: str
    chunks_count: int



class IndexTaskInfo(BaseModel):
    original_file_name: str
    chunks_count: int
    task_id: str
    status: TaskStatus = TaskStatus.PENDING


class BatchIndexResponse(BaseModel):
    message: str = "Files indexing queued."
    tasks: list[IndexTaskInfo]
    total: int = Field(default=0)

    @model_validator(mode="after")
    def set_total(self) -> "BatchIndexResponse":
        self.total = len(self.tasks)
        return self
    





class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: dict | None = None
    error: str | None = None
