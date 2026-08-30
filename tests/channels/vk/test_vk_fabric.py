from unittest.mock import MagicMock

import pytest

from microclaw.channels.vk.fabric import get_vk_channel
from microclaw.channels.vk.polling import VKPollingChannel
from microclaw.channels.vk.settings import VKMethodEnum, VKSettings
from microclaw.channels.vk.webhook import VKWebhookChannel


class TestGetVKChannel:
    @pytest.fixture
    def settings(self):
        return VKSettings(token="test_token")

    @pytest.fixture
    def dependencies(self):
        return {
            "agent": MagicMock(),
            "sessions_storage": MagicMock(),
            "syncer": MagicMock(),
            "users_storage": MagicMock(),
            "resolver": MagicMock(),
            "bot": MagicMock(),
        }

    def test_polling(self, settings, dependencies):
        settings.method = VKMethodEnum.POLLING
        channel = get_vk_channel(settings=settings, **dependencies)
        assert isinstance(channel, VKPollingChannel)

    def test_webhook(self, settings, dependencies):
        settings.method = VKMethodEnum.WEBHOOK
        channel = get_vk_channel(settings=settings, **dependencies)
        assert isinstance(channel, VKWebhookChannel)

    def test_unsupported_method(self, settings, dependencies):
        settings.method = "unknown"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unsupported vk service"):
            get_vk_channel(settings=settings, **dependencies)
