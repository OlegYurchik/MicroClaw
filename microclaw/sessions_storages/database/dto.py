from datetime import datetime
import uuid

from pydantic import BaseModel

from microclaw.dto import Spending


class SessionData(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    channel_key: str = ""
    channel_internal_id: str = ""
    context_size: int = 0
    spending: Spending | None = None
