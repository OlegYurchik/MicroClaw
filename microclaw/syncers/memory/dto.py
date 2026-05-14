from pydantic import BaseModel


class StorageItem(BaseModel):
    value: object
    expire_at: float | None = None
