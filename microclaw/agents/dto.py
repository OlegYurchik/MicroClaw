from dataclasses import dataclass, field

from langchain_core.tools import BaseTool
from pydantic import AwareDatetime, BaseModel

from .settings import AgentIdentity
from microclaw.toolkits.base import BaseToolKit


class MCPInfo(BaseModel):
    name: str
    description: str | None = None


class SystemValues(BaseModel):
    time: AwareDatetime
    timezone: str = "UTC"


@dataclass
class AgentPromptValues:
    agent_identity: AgentIdentity
    system: SystemValues
    max_tool_calls: int = 25
    toolkits: dict[str, BaseToolKit] = field(default_factory=dict)
    tools: list[BaseTool] = field(default_factory=list)
    channel: "BaseChannel" = None  # noqa: F821
    memories: dict[str, str] = field(default_factory=dict)
    subagents: list["SubAgentToolKit"] = field(default_factory=list)  # noqa: F821
    mcps: dict[str, MCPInfo] = field(default_factory=dict)


@dataclass
class SummaryValues:
    context: str
    max_tokens: int


@dataclass
class SummaryMemoryValues:
    old_context: str
    new_context: str
    max_tokens: int
