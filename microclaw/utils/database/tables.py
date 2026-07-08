from typing import Any, Self

from pydantic import BaseModel
from sqlmodel import SQLModel


class BaseTable(SQLModel):
    @classmethod
    def from_item(cls, item: BaseModel) -> Self:
        raise NotImplementedError

    def to_item(self) -> BaseModel:
        raise NotImplementedError

    def to_values(self) -> dict[str, Any]:
        return {
            column.name: getattr(self, column.name) for column in self.__table__.columns
        }
