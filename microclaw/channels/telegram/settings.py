import enum
from typing import Literal

from microclaw.channels.settings import ChannelSettings, ChannelTypeEnum


class TelegramMethodEnum(str, enum.Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class TelegramIPFamilyEnum(str, enum.Enum):
    AUTO = "auto"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


class TelegramSettings(ChannelSettings):
    type: Literal[ChannelTypeEnum.TELEGRAM] = ChannelTypeEnum.TELEGRAM
    method: TelegramMethodEnum = TelegramMethodEnum.POLLING
    ip_family: TelegramIPFamilyEnum = TelegramIPFamilyEnum.AUTO
    token: str
    name: str = "MicroClaw 🤖"
    allow_from: list[int | str] | None = None
    show_context_usage: bool = False
    show_costs: bool = False
    debug: bool = False
