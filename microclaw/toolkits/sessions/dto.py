from uuid import UUID

from pydantic import AwareDatetime, BaseModel


class MessageInfo(BaseModel):
    role: str
    content: str | None
    timestamp: AwareDatetime


class SessionInfo(BaseModel):
    session_id: UUID
    messages: list[MessageInfo] = []
    message_count: int = 0
    user_id: UUID | None = None
    created_at: AwareDatetime | None = None
    last_activity: AwareDatetime | None = None


class SearchResult(BaseModel):
    session_id: UUID
    matched_messages: list[MessageInfo] = []
    match_count: int = 0
