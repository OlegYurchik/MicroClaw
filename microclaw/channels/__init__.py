from .fabric import get_channel
from .interfaces import ChannelInterface
from .telegram.polling import TelegramPollingSettings
from .telegram.webhook import TelegramWebhookSettings
from .settings import ChannelSettings, ChannelTypeEnum


ChannelSettingsType = (
    TelegramPollingSettings |
    TelegramWebhookSettings
)


__all__ = (
    "ChannelSettingsType",
    # fabric
    "get_channel",
    # interfaces
    "ChannelInterface",
    # settings
    "ChannelSettings",
    "ChannelTypeEnum",
)
