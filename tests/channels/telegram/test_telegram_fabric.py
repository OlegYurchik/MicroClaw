from unittest.mock import MagicMock

import pytest

from microclaw.channels.telegram.fabric import get_telegram_channel
from microclaw.channels.telegram.polling import TelegramPollingChannel
from microclaw.channels.telegram.settings import TelegramMethodEnum, TelegramSettings
from microclaw.channels.telegram.webhook import TelegramWebhookChannel
from microclaw.channels.telegram.webhook.settings import TelegramWebhookSettings


class TestGetTelegramChannel:
    @pytest.fixture
    def polling_settings(self):
        return TelegramSettings(
            token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            allow_from=["*"],
        )

    @pytest.fixture
    def webhook_settings(self):
        return TelegramWebhookSettings(
            token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            allow_from=["*"],
        )

    @pytest.fixture
    def dependencies(self):
        return {
            "agent": MagicMock(),
            "sessions_storage": MagicMock(),
            "syncer": MagicMock(),
            "users_storage": MagicMock(),
            "resolver": MagicMock(),
        }

    def test_polling(self, polling_settings, dependencies):
        polling_settings.method = TelegramMethodEnum.POLLING
        channel = get_telegram_channel(settings=polling_settings, **dependencies)
        assert isinstance(channel, TelegramPollingChannel)

    def test_webhook(self, webhook_settings, dependencies):
        webhook_settings.method = TelegramMethodEnum.WEBHOOK
        channel = get_telegram_channel(settings=webhook_settings, **dependencies)
        assert isinstance(channel, TelegramWebhookChannel)

    def test_unsupported_method(self, polling_settings, dependencies):
        polling_settings.method = "unknown"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unsupported telegram service"):
            get_telegram_channel(settings=polling_settings, **dependencies)
