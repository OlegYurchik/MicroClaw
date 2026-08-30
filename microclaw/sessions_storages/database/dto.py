from datetime import datetime
import uuid

from pydantic import BaseModel

from microclaw.dto import Spending


class SessionData(BaseModel):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    context: int = 0
    spending: Spending | None = None
