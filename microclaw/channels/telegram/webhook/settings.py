from typing import Literal

from pydantic import HttpUrl, conint, field_validator

from microclaw.channels.telegram.settings import TelegramMethodEnum, TelegramSettings
from .cloudflare.settings import CloudflareTunnelSettings


class TelegramWebhookSettings(TelegramSettings):
    method: Literal[TelegramMethodEnum.WEBHOOK] = TelegramMethodEnum.WEBHOOK

    root_url: HttpUrl | None = None
    root_path: str = "/"

    port: conint(ge=1, le=65535) = 8000
    secret_access_key: str = "webhooksuperpupersecretaccesskey"

    cloudflare_tunnel: CloudflareTunnelSettings = CloudflareTunnelSettings()

    @field_validator("cloudflare_tunnel")
    @classmethod
    def validate_cloudflare_compatibility(cls, v: CloudflareTunnelSettings, info):
        if v.enabled and info.data.get("root_url") is not None:
            raise ValueError("root_url cannot be set when cloudflare_tunnel.enabled is true")
        return v