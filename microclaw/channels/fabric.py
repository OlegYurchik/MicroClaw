from microclaw.agents import Agent
from microclaw.sessions_storages import SessionsStorageInterface
from .interfaces import ChannelInterface
from .settings import ChannelSettings, ChannelTypeEnum
from .telegram import get_telegram_channel


def get_channel(
        settings: ChannelSettings,
        agent: Agent,
        sessions_storage: SessionsStorageInterface,
        channel_key: str = "default",
) -> ChannelInterface:
    match settings.type:
        case ChannelTypeEnum.TELEGRAM:
            return get_telegram_channel(
                settings=settings,
                agent=agent,
                sessions_storage=sessions_storage,
                channel_key=channel_key,
            )
        case _:
            raise ValueError(f"Unsupported channel type: {settings.type.value}")
