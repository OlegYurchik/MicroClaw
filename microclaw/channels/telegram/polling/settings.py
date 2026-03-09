from typing import Literal

from pydantic import PositiveInt

from microclaw.channels.telegram.settings import TelegramMethodEnum, TelegramSettings


class TelegramPollingSettings(TelegramSettings):
    method: Literal[TelegramMethodEnum.POLLING] = (
        TelegramMethodEnum.POLLING
    )

    timeout: PositiveInt = 10  # in seconds
