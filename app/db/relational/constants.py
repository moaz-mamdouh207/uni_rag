from enum import Enum

class DocumentStatus(str, Enum):
    UPLOADED   = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    CHUNKED    = "CHUNKED"
    EMBEDDING  = "EMBEDDING"
    INDEXED    = "INDEXED"
    FAILED     = "FAILED"

class ChunkType(str, Enum):
    THEORY = "theory"
    SOLVED_QUESTION = "solved_question"
    UNSOLVED_QUESTION = "unsolved_question"

class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
