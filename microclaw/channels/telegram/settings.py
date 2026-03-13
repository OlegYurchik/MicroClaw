import enum
from typing import Literal

from microclaw.channels.settings import ChannelSettings, ChannelTypeEnum


class TelegramMethodEnum(str, enum.Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class TelegramSettings(ChannelSettings):
    type: Literal[ChannelTypeEnum.TELEGRAM] = ChannelTypeEnum.TELEGRAM
    method: TelegramMethodEnum = TelegramMethodEnum.POLLING
    token: str
    name: str = "MicroClaw 🤖" 
    allow_from: list[int | str] | None = None
    show_context_usage: bool = False
    show_costs: bool = False
    debug: bool = False
