import uuid

from pydantic import BaseModel, Field


class TokenCreateRequest(BaseModel):
    user_id: uuid.UUID
    ttl_days: int = Field(default=30, ge=1, le=365)
