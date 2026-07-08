from pydantic import BaseModel, conint, model_validator


class CloudflareTunnelSettings(BaseModel):
    enabled: bool = False
    tunnel_name: str = "telegram-bot-tunnel"
    path: str | None = None
    timeout: conint(ge=10, le=600) = 30
    version: str = "2025.5.0"

    @model_validator(mode="after")
    def validate_required_fields(self):
        if self.enabled:
            if not self.tunnel_name or not self.tunnel_name.strip():
                raise ValueError("tunnel_name is required when enabled is True")
            if self.path is not None and not self.path.strip():
                raise ValueError("path cannot be empty when set")
        return self
