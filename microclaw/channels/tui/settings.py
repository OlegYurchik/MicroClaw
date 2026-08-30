from typing import Literal

from microclaw.channels.settings import ChannelSettings, ChannelTypeEnum


class TUIChannelSettings(ChannelSettings):
    type: Literal[ChannelTypeEnum.TUI] = ChannelTypeEnum.TUI
    debug: bool = False
