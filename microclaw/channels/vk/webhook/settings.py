from typing import Literal

from pydantic import HttpUrl, conint, constr

from microclaw.channels.vk.settings import VKMethodEnum, VKSettings


class VKWebhookSettings(VKSettings):
    method: Literal[VKMethodEnum.WEBHOOK] = VKMethodEnum.WEBHOOK

    root_url: HttpUrl
    root_path: str = ""
    secret_access_key: str | None = None
    title: constr(max_length=14) = "MicroClaw"

    host: str = "0.0.0.0"
    port: conint(ge=1, le=65535) = 8000
