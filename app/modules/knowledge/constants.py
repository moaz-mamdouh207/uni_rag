from enum import Enum

class SavingMessages(str, Enum): 
    FILE_EXISTS = "File named as {file_name} with the same content already exists."
    FILE_SAVED = "File saved successfuly"
    UPLOAD_QUEUED = "Files ingestion queued"