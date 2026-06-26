from microclaw.agents import Agent
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from .base import BaseVKChannel
from .polling import VKPollingChannel
from .settings import VKMethodEnum, VKSettings
from .webhook import VKWebhookChannel


def get_vk_channel(
        settings: VKSettings,
        agent: Agent,
        sessions_storage: SessionsStorageInterface,
        syncer: SyncerInterface,
        users_storage: UsersStorageInterface,
        resolver: "DependencyResolver",  # noqa: F821
        stt: STT | None = None,
        channel_key: str = "default",
) -> BaseVKChannel:
    match settings.method:
        case VKMethodEnum.POLLING:
            return VKPollingChannel(
                settings=settings,
                agent=agent,
                sessions_storage=sessions_storage,
                stt=stt,
                channel_key=channel_key,
                syncer=syncer,
                users_storage=users_storage,
                resolver=resolver,
            )
        case VKMethodEnum.WEBHOOK:
            return VKWebhookChannel(
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
            raise ValueError(f"Unsupported vk service with method: '{settings.method}'")
