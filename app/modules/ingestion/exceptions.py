class IngestionError(Exception):
    """Base exception for the ingestion module."""
    pass

class LoaderError(IngestionError):
    """Raised when a loader fails to process a file."""
    pass