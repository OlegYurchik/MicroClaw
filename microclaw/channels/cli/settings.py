from typing import Literal

from microclaw.channels.settings import ChannelTypeEnum, ChannelSettings


class CLIChannelSettings(ChannelSettings):
    type: Literal[ChannelTypeEnum.CLI] = ChannelTypeEnum.CLI
    show_loader: bool = False
    show_costs: bool = False
    show_context_usage: bool = False
    debug: bool = False
