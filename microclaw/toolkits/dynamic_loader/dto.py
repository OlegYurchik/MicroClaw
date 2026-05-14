from pydantic import BaseModel


class ToolKitInfo(BaseModel):
    name: str
    description: str | None = None
    tools: list[str] = []


class ToolInfo(BaseModel):
    name: str
    description: str | None = None
