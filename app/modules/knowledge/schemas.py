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


from pydantic import BaseModel, Field

class PageRangeRequest(BaseModel):
    start_page: int = Field(..., ge=1, description="Starting page number (1-indexed)")
    end_page: int = Field(..., ge=1, description="Ending page number (inclusive, max 20 pages per request)")

    model_config = {"json_schema_extra": {"example": {"start_page": 1, "end_page": 5}}}

class PageImageItem(BaseModel):
    page_number: int
    image: str  # base64-encoded PNG

class PageImagesResponse(BaseModel):
    pages: list[PageImageItem]