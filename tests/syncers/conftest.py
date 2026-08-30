import pytest

from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer


@pytest.fixture
def memory_syncer() -> MemorySyncer:
    return MemorySyncer(settings=MemorySyncerSettings())
