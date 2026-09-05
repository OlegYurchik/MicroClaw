from unittest.mock import AsyncMock, MagicMock, patch

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
    @patch.object(DependencyResolver, "resolve_agents", new_callable=AsyncMock)
    def test_create_tui_channel_success(self, mock_resolve, minimal_settings):
        mock_resolve.return_value = {"default": MagicMock()}
        channel = create_tui_channel(
            settings=minimal_settings,
            debug=True,
        )

        assert channel is not None
        assert channel._settings.debug is True
        mock_resolve.assert_awaited_once()

    def test_create_tui_channel_no_agents_raises(self, minimal_settings):
        settings = minimal_settings.model_copy(update={"agents": {}})
        with pytest.raises(ValueError, match="agents"):
            create_tui_channel(settings=settings)

    def test_create_tui_channel_no_sessions_storage_raises(self, minimal_settings):
        settings = minimal_settings.model_copy(update={"sessions_storages": {}})
        with pytest.raises(ValueError, match="sessions storage"):
            create_tui_channel(settings=settings)

    def test_create_tui_channel_no_users_storage_raises(self, minimal_settings):
        settings = minimal_settings.model_copy(update={"users_storages": {}})
        with pytest.raises(ValueError, match="users storage"):
            create_tui_channel(settings=settings)

    @patch.object(DependencyResolver, "resolve_agents", new_callable=AsyncMock)
    def test_create_tui_channel_uses_defaults(self, mock_resolve, minimal_settings):
        mock_resolve.return_value = {"default": MagicMock()}
        channel = create_tui_channel(
            settings=minimal_settings,
        )

        assert channel is not None
        assert isinstance(channel._settings, TUIChannelSettings)
        mock_resolve.assert_awaited_once()
