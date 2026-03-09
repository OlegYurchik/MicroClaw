from microclaw.agents import Agent
from microclaw.sessions_storages import SessionsStorageInterface
from .base import BaseTelegramChannel
from .polling import TelegramPollingChannel
from .settings import TelegramMethodEnum, TelegramSettings
from .webhook import TelegramWebhookChannel


def get_telegram_channel(
        settings: TelegramSettings,
        agent: Agent,
        sessions_storage: SessionsStorageInterface,
        channel_key: str = "default",
) -> BaseTelegramChannel:
    match settings.method:
        case TelegramMethodEnum.POLLING:
            return TelegramPollingChannel(
                settings=settings,
                agent=agent,
                sessions_storage=sessions_storage,
                channel_key=channel_key,
            )
        case TelegramMethodEnum.WEBHOOK:
            return TelegramWebhookChannel(
                settings=settings,
                agent=agent,
                sessions_storage=sessions_storage,
                channel_key=channel_key,
            )
        case _:
            raise ValueError(f"Unsupported telegram service with method: '{settings.method}'")
