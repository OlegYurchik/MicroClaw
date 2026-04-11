from pydantic import BaseModel, Field


class CommandToolKitSettings(BaseModel):
    """Settings for the command toolkit."""

    allowed_commands: list[str] = Field(
        default_factory=lambda: ["ls", "cat", "grep", "find"],
        description="List of allowed commands to execute",
    )
