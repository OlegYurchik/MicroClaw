from .base import BaseChannel
from .fabric import get_channel
from .telegram.polling import TelegramPollingSettings
from .telegram.webhook import TelegramWebhookSettings
from .matrix.settings import MatrixSettings
from .settings import ChannelSettings, ChannelTypeEnum


ChannelSettingsType = (
    TelegramPollingSettings |
    TelegramWebhookSettings |
    MatrixSettings
)


__all__ = (
    "ChannelSettingsType",
    # base
    "BaseChannel",
    # fabric
    "get_channel",
    # interfaces
    # settings
    "ChannelSettings",
    "ChannelTypeEnum",
)
