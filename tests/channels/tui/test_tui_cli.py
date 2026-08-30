from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.channels.tui.cli import create_tui_channel
from microclaw.channels.tui.settings import TUIChannelSettings
from microclaw.resolver import DependencyResolver
from microclaw.settings import MicroclawSettings


@pytest.fixture
def minimal_settings() -> MicroclawSettings:
    return MicroclawSettings(
        agents={"default": {}},
        sessions_storages={"default": {"type": "memory"}},
        users_storages={"default": {"type": "memory"}},
        syncer={"type": "memory"},
    )


class TestCreateTUIChannel:
    def test_create_tui_channel_success(self, minimal_settings):
        resolver = MagicMock(spec=DependencyResolver)
        resolver.resolve_agents = AsyncMock(return_value={"default": MagicMock()})

        sessions_storage = MagicMock()
        users_storage = MagicMock()
        syncer = MagicMock()

        channel = create_tui_channel(
            settings=minimal_settings,
            debug=True,
            resolver=resolver,
            sessions_storage_factory=lambda settings: sessions_storage,
            users_storage_factory=lambda settings: users_storage,
            syncer_factory=lambda settings: syncer,
        )

        assert channel is not None
        assert channel._settings.debug is True
        resolver.resolve_agents.assert_called()

    def test_create_tui_channel_no_agents_raises(self, minimal_settings):
        settings = minimal_settings.model_copy(update={"agents": {}})
        with pytest.raises(ValueError, match="agents"):
            create_tui_channel(settings=settings)

    def test_create_tui_channel_no_sessions_storage_raises(self, minimal_settings):
        settings = minimal_settings.model_copy(update={"sessions_storages": {}})
        resolver = MagicMock(spec=DependencyResolver)
        resolver.resolve_agents = AsyncMock(return_value={"default": MagicMock()})
        with pytest.raises(ValueError, match="sessions storage"):
            create_tui_channel(settings=settings, resolver=resolver)

    def test_create_tui_channel_no_users_storage_raises(self, minimal_settings):
        settings = minimal_settings.model_copy(update={"users_storages": {}})
        resolver = MagicMock(spec=DependencyResolver)
        resolver.resolve_agents = AsyncMock(return_value={"default": MagicMock()})
        with pytest.raises(ValueError, match="users storage"):
            create_tui_channel(settings=settings, resolver=resolver)

    def test_create_tui_channel_uses_defaults(self, minimal_settings):
        resolver = MagicMock(spec=DependencyResolver)
        resolver.resolve_agents = AsyncMock(return_value={"default": MagicMock()})

        channel = create_tui_channel(
            settings=minimal_settings,
            resolver=resolver,
        )

        assert channel is not None
        assert isinstance(channel._settings, TUIChannelSettings)
