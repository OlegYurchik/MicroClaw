import enum
from typing import Literal

from microclaw.channels.settings import ChannelSettings, ChannelTypeEnum


class VKMethodEnum(str, enum.Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class VKSettings(ChannelSettings):
    type: Literal[ChannelTypeEnum.VK] = ChannelTypeEnum.VK
    method: VKMethodEnum = VKMethodEnum.POLLING
    token: str
    name: str = "MicroClaw 🤖"
    allow_from: list[int | str] | None = None
    show_context_usage: bool = False
    show_costs: bool = False
    debug: bool = False
    root_url: str | None = None
    root_path: str = ""
    host: str = "0.0.0.0"
    port: int = 8080
    title: str = "MicroClaw"
    secret_access_key: str | None = None
