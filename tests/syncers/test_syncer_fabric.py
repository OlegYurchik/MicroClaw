import pytest

from microclaw.syncers.fabric import get_syncer
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer


class TestGetSyncer:
    def test_memory(self):
        settings = MemorySyncerSettings()
        result = get_syncer(settings)
        assert isinstance(result, MemorySyncer)

    def test_unsupported_raises(self):
        class FakeType:
            value = "unsupported"

        class FakeSettings:
            type = FakeType()

        with pytest.raises(ValueError, match="Unsupported syncer type"):
            get_syncer(FakeSettings())
