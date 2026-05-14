from pydantic import BaseModel, Field

from microclaw.toolkits import ToolKitSettings


class DynamicLoaderToolKitSettings(BaseModel):
    toolkits: dict[str, ToolKitSettings | str] = Field(default_factory=dict)
