from typing import Literal

from microclaw.syncers.settings import SyncerSettings, SyncerTypeEnum


class MemorySyncerSettings(SyncerSettings):
    type: Literal[SyncerTypeEnum.MEMORY] = SyncerTypeEnum.MEMORY
