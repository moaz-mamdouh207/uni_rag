from enum import Enum

class ErrorMessages(str, Enum):
    COURSE_NOT_FOUND = "no course found with this name"
    