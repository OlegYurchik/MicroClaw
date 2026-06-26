from typing import Any

from pydantic import BaseModel, Field


class LangChainToolkitAdapterSettings(BaseModel):
    toolkit_class: str
    args: dict[str, Any] = Field(default_factory=dict)
    selected_tools: list[str] | None = None
