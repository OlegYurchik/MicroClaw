import uuid

from pydantic import BaseModel, Field

from microclaw.dto import AgentMessage, AgentMessageRoleEnum, Spending


__all__ = (
    "MessageCreate",
    "MessageUpdate",
    "SessionCreate",
    "SessionUpdate",
)


class SessionUpdate(BaseModel):
    context_size: int | None = None
    spending: Spending | None = None


class SessionCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    channel_key: str
    channel_internal_id: str


class MessageCreate(BaseModel):
    session_id: uuid.UUID
    message: AgentMessage


class MessageUpdate(BaseModel):
    role: AgentMessageRoleEnum | None = None
    text: str | None = None
