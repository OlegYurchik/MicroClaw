from datetime import datetime
from pydantic import BaseModel
from uuid import UUID


class MessageInfo(BaseModel):
    role: str
    content: str | None
    timestamp: datetime


class SessionInfo(BaseModel):
    session_id: UUID
    messages: list[MessageInfo] = []
    message_count: int = 0
    user_id: UUID | None = None
    created_at: datetime | None = None
    last_activity: datetime | None = None


class SearchResult(BaseModel):
    session_id: UUID
    matched_messages: list[MessageInfo] = []
    match_count: int = 0
