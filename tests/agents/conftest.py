import pytest

from microclaw.agents.checkpointer import SyncerCheckpointer
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer


@pytest.fixture
def syncer():
    return MemorySyncer(settings=MemorySyncerSettings())


@pytest.fixture
def checkpointer(syncer):
    return SyncerCheckpointer(syncer)
