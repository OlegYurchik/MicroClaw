from .base import BaseChannel
from .fabric import get_channel
from .settings import ChannelSettings, ChannelTypeEnum
from .telegram.polling.settings import TelegramPollingSettings
from .telegram.webhook.settings import TelegramWebhookSettings
from .vk.polling.settings import VKPollingSettings
from .vk.webhook.settings import VKWebhookSettings


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
