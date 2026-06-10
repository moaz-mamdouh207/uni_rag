from pydantic import BaseModel
from uuid import UUID

# ── Responses ─────────────────────────────────────────────────────────────────
class CourseMetadata(BaseModel):
    "The metadata exposed to the front end"
    id: UUID
    name: str


class DocumentMetadata(BaseModel):
    "The metadata exposed to the front end"
    id: UUID
    name: str


class UploadTaskInfo(BaseModel):
    id: UUID
    name: str
    task_id: str
