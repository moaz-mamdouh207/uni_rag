from enum import Enum

class AttachmentType(str, Enum):
    PDF = "pdf"
    PNG = "image/png"
    JPEG = "image/jpeg"
    WEBP = "image/webp"

ALLOWED_ATTACHEMENTS = {item.value for item in AttachmentType}