from enum import Enum

class ErrorMessages(str, Enum):
    FORBIDDEN_ACCESS = "You do not have permission to access this resource."
    INVALID_TYPE = "Invalid file type. Magic bytes do not match allowed types."
    FILE_TOO_LARGE = "File exceeds the maximum file size limit."
    MISSING_FILENAME = "Filename is missing."
    CORRUPTED_FILE = "Could not read file content."
    FILE_SAVE_FAILED="saving given file failed, please try again later"
    COURSE_NOT_FOUND = "no course found with this name"