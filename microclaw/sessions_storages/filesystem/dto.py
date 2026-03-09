from pydantic import BaseModel, Field

from microclaw.dto import AgentMessage, Spending


class SessionData(BaseModel):
    messages: list[AgentMessage] = Field(default_factory=list)
    spending: Spending = Field(default_factory=Spending)
