from .base import BaseChannel
from .fabric import get_channel
from .telegram.polling import TelegramPollingSettings
from .telegram.webhook import TelegramWebhookSettings
from .vk.polling import VKPollingSettings
from .vk.webhook import VKWebhookSettings
from .settings import ChannelSettings, ChannelTypeEnum


ChannelSettingsType = (
    TelegramPollingSettings
    | TelegramWebhookSettings
    | VKPollingSettings
    | VKWebhookSettings
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
