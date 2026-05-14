from typing import Any

from sqlmodel import SQLModel


class DatabaseException(Exception):
    pass


class HaveNoSessionError(DatabaseException):
    def __init__(self):
        super().__init__("Have no actual session")


class AlreadyExistsError(DatabaseException):
    def __init__(self, model: SQLModel, values: dict[str, Any]):
        super().__init__(f"Record for model '{model.__name__}' already exists")

        self.model = model
        self.values = values
