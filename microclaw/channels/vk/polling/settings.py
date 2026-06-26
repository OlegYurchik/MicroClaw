from typing import Literal

from microclaw.channels.vk.settings import VKMethodEnum, VKSettings


class VKPollingSettings(VKSettings):
    method: Literal[VKMethodEnum.POLLING] = VKMethodEnum.POLLING
