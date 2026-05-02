from typing import Any

from pydantic import BaseModel, Field


class CronTaskSettings(BaseModel):
    path: str = "microclaw.cron.tasks.agent.AgentCronTask"
    cron: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
