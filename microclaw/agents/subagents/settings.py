from typing import Any

from pydantic import BaseModel, Field


class SubAgentSettings(BaseModel):
    name: str
    agent: dict[str, Any] | str
    description: str | None = None
    max_turns: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of conversation turns with subagent",
    )
    summarize_threshold_tokens: int | None = Field(
        default=None,
        ge=1,
        description="Token threshold for triggering summarization. None means no summarization",
    )
