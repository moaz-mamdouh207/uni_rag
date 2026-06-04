class UploadError(Exception):
    """Base exception for the upload module."""
    pass

class FileDuplicateError(UploadError):
    def __init__(self, file_name: str):
        super().__init__(f"File already exists: {file_name}")
        self.file_name = file_name

class ManifestError(UploadError):
    pass
