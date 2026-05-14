from microclaw.syncers.interfaces import SyncerInterface
from microclaw.syncers.memory import MemorySyncer
from microclaw.syncers.settings import SyncerSettings, SyncerTypeEnum


def get_syncer(settings: SyncerSettings) -> SyncerInterface:
    match settings.type:
        case SyncerTypeEnum.MEMORY:
            return MemorySyncer(settings=settings)
        case _:
            raise ValueError(f"Unsupported syncer type: {settings.type.value}")
