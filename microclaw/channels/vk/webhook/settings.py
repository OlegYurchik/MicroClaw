from typing import Literal

from pydantic import HttpUrl, conint

from microclaw.channels.vk.settings import VKMethodEnum, VKSettings


class VKWebhookSettings(VKSettings):
    method: Literal[VKMethodEnum.WEBHOOK] = VKMethodEnum.WEBHOOK

    root_url: HttpUrl
    root_path: str = "/"

    host: str = "0.0.0.0"
    port: conint(ge=1, le=65535) = 8000
