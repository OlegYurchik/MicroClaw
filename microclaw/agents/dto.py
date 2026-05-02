import datetime
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool
from pydantic import AwareDatetime, BaseModel

from .settings import AgentIdentity
from microclaw.toolkits.base import BaseToolKit


class SystemValues(BaseModel):
    time: AwareDatetime
    timezone: str = "UTC"


@dataclass
class SystemPromptValues:
    agent_identity: AgentIdentity
    system: SystemValues
    toolkits: dict[str, BaseToolKit] = field(default_factory=dict)
    tools: list[BaseTool] = field(default_factory=list)
    channel: "BaseChannel" = None
    memories: dict[str, str] = field(default_factory=dict)
    subagents: list["SubAgentToolKit"] = field(default_factory=list)


@dataclass
class SummaryValues:
    context: str
    max_tokens: int


@dataclass
class SummaryMemoryValues:
    old_context: str
    additional_context: str
    max_tokens: int
