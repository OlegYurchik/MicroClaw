from pydantic import BaseModel, Field


class HomeAssistantSettings(BaseModel):
    """Settings for connecting to Home Assistant."""

    url: str = Field(
        description=(
            "URL of the Home Assistant instance "
            "(e.g., http://homeassistant.local:8123)"
        ),
    )
    token: str = Field(
        description="Long-lived access token for authentication",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificate (default: True)",
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds (default: 30)",
    )
