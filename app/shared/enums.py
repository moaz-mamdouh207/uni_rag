from enum import Enum

class FileType(str, Enum):
    PDF = "application/pdf"

    DOC = "application/msword"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    PPT = "application/vnd.ms-powerpoint"
    PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

ALLOWED_KNOWLEDGE = {item.value for item in FileType}
