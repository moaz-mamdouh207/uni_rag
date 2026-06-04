from enum import Enum

class UploadErrorMessages(str, Enum):
    INVALID_TYPE = "Invalid file type. Magic bytes do not match allowed types."
    FILE_TOO_LARGE = "File exceeds the maximum file size limit."
    MISSING_FILENAME = "Filename is missing."
    CORRUPTED_FILE = "Could not read file content."
    FILE_SAVE_FAILED="saving given file failed, please try again later"
    COURSE_NOT_FOUND = "no course found with this name"
    
class SavingMessages(str, Enum): 
    FILE_EXISTS = "File named as {file_name} with the same content already exists."
    FILE_SAVED = "File saved successfuly"
    UPLOAD_QUEUED = "Files ingestion queued"