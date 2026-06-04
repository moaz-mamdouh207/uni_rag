from enum import Enum

class ErrorMessages(str, Enum):
    FORBIDDEN_ACCESS = "You do not have permission to access this resource."