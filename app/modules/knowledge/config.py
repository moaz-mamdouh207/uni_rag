from pydantic import BaseModel

class DocumentSettings(BaseModel):
    max_document_size_in_mbs: int = 10
    buffer_size_in_mbs: int = 5
