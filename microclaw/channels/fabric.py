from microclaw.agents import Agent
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from .base import BaseChannel
from .settings import ChannelSettings, ChannelTypeEnum
from .telegram import get_telegram_channel
from .matrix.channel import MatrixChannel


def get_channel(
        settings: ChannelSettings,
        agent: Agent,
        sessions_storage: SessionsStorageInterface,
        syncer: SyncerInterface,
        users_storage: UsersStorageInterface,
        resolver: "DependencyResolver",
        stt: STT | None = None,
        channel_key: str = "default",
) -> BaseChannel:
    match settings.type:
        case ChannelTypeEnum.TELEGRAM:
            return get_telegram_channel(
                settings=settings,
                agent=agent,
                sessions_storage=sessions_storage,
                stt=stt,
                channel_key=channel_key,
                syncer=syncer,
                users_storage=users_storage,
                resolver=resolver,
            )
        case ChannelTypeEnum.MATRIX:
            return MatrixChannel(
                settings=settings,
                agent=agent,
                sessions_storage=sessions_storage,
                stt=stt,
                channel_key=channel_key,
                syncer=syncer,
                users_storage=users_storage,
                resolver=resolver,
            )
        case _:
            raise ValueError(f"Unsupported channel type: {settings.type.value}")
