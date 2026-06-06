from enum import Enum

class FileType(str, Enum):
    PDF = "application/pdf"

    DOC = "application/msword"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    PPT = "application/vnd.ms-powerpoint"
    PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

ALLOWED_KNOWLEDGE = {item.value for item in FileType}

class TempFileType(str, Enum):
    PDF = "pdf"
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"

ALLOWED_ATTACHEMENTS = {item.value for item in TempFileType}
