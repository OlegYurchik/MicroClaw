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
    toolkits: list[BaseToolKit] = field(default_factory=list)
    tools: list[BaseTool] = field(default_factory=list)
    channel: "ChannelInterface" = None
