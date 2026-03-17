from typing import Any

from pydantic import BaseModel, Field

from microclaw.agents import AgentSettings
from microclaw.channels import ChannelSettingsType


class CronSettings(BaseModel):
    task: str
    cron: str = "*/30 * * * *"
    channel: ChannelSettingsType | str | None = None
    channel_args: dict[str, Any] = Field(default_factory=dict)
