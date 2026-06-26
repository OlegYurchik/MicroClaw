from typing import Any

from pydantic import BaseModel, Field, PositiveInt


class SubAgentSettings(BaseModel):
    name: str
    agent: dict[str, Any] | str
    description: str | None = None
    max_turns: PositiveInt | None = None
