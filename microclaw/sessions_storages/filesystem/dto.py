from pydantic import BaseModel, Field

from microclaw.dto import AgentMessage, Spending


class SessionData(BaseModel):
    channel_key: str = ""
    channel_internal_id: str = ""
    messages: list[AgentMessage] = Field(default_factory=list)
    spending: Spending | None = None
    context: int = 0
