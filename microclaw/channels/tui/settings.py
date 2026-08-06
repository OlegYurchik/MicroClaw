from typing import Literal

from microclaw.channels.settings import ChannelTypeEnum, ChannelSettings


class TUIChannelSettings(ChannelSettings):
    type: Literal[ChannelTypeEnum.TUI] = ChannelTypeEnum.TUI
    debug: bool = False
