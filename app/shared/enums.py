from enum import Enum

class FileType(str, Enum):
    PDF = "application/pdf"

    DOC = "application/msword"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    PPT = "application/vnd.ms-powerpoint"
    PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    # PNG = "image/png"
    # JPEG = "image/jpeg"
    # WEBP = "image/webp"


ALLOWED_KNOWLEDGE = {item.value for item in FileType}
