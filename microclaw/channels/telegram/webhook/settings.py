from typing import Literal

from pydantic import AnyHttpUrl, conint, constr

from microclaw.channels.telegram.settings import TelegramMethodEnum, TelegramSettings


class TelegramWebhookSettings(TelegramSettings):
    method: Literal[TelegramMethodEnum.WEBHOOK] = TelegramMethodEnum.WEBHOOK

    root_url: AnyHttpUrl
    root_path: str = "/"
    port: conint(ge=1, le=65535) = 8000
    secret_access_key: constr(pattern=r"^\w{32}$") = "webhooksuperpupersecretaccesskey"
