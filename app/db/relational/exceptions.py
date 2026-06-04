class RepositoryError(Exception):
    """Base exception for all Repository errors."""


class NotFoundError(RepositoryError):
    """Raised when a document cannot be found by the given identifier."""

    def __init__(self, entity: str, id: str) -> None:
        super().__init__(f"{entity} not found: {id}")
        self.identifier = id


class DBIntegrityError(RepositoryError):
    """Raised when a database integrity constraint is violated."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Integrity error: {detail}")


class DatabaseError(RepositoryError):
    """Raised for unexpected database-level errors."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Database error: {detail}")