from .base import BaseChannel
from .fabric import get_channel
from .telegram.polling import TelegramPollingSettings
from .telegram.webhook import TelegramWebhookSettings
from .settings import ChannelSettings, ChannelTypeEnum


ChannelSettingsType = (
    TelegramPollingSettings |
    TelegramWebhookSettings
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
