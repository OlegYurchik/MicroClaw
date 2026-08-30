from unittest.mock import AsyncMock, MagicMock

from aiogram import Bot, Dispatcher
import pytest

from microclaw.channels.telegram.webhook.channel import TelegramWebhookChannel
from microclaw.channels.telegram.webhook.cloudflare import CloudflareTunnelService
from microclaw.channels.telegram.webhook.settings import TelegramWebhookSettings
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def telegram_webhook_settings() -> TelegramWebhookSettings:
    return TelegramWebhookSettings(
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        allow_from=[],
        root_url="http://localhost:8080",
        root_path="/webhook",
        port=8000,
    )


@pytest.fixture
def telegram_webhook_settings_cloudflare() -> TelegramWebhookSettings:
    return TelegramWebhookSettings(
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        allow_from=[],
        root_path="/webhook",
        port=8000,
        cloudflare_tunnel={"enabled": True, "tunnel_name": "test"},
    )


@pytest.fixture
def mock_bot() -> MagicMock:
    bot = MagicMock(spec=Bot)
    bot.set_webhook = AsyncMock()
    return bot


@pytest.fixture
def mock_dispatcher() -> MagicMock:
    dispatcher = MagicMock(spec=Dispatcher)
    dispatcher.message = MagicMock()
    dispatcher.message.middleware = MagicMock()
    dispatcher.callback_query = MagicMock()
    dispatcher.callback_query.return_value = MagicMock()
    return dispatcher


@pytest.fixture
def mock_cloudflare_service() -> MagicMock:
    service = MagicMock(spec=CloudflareTunnelService)
    service.get_public_url = AsyncMock(return_value="https://test.example.com")
    return service


@pytest.fixture
def mock_server() -> MagicMock:
    server = MagicMock()
    server.serve = AsyncMock()
    return server


@pytest.fixture
def mock_server_factory(mock_server):
    def _factory(config):
        return mock_server

    return _factory


@pytest.fixture
def telegram_webhook_channel(
    telegram_webhook_settings,
    telegram_agent,
    mock_bot,
    mock_dispatcher,
    mock_server_factory,
) -> TelegramWebhookChannel:
    return TelegramWebhookChannel(
        settings=telegram_webhook_settings,
        agent=telegram_agent,
        sessions_storage=MemorySessionsStorage(
            settings=MemorySessionsStorageSettings()
        ),
        syncer=MemorySyncer(settings=MemorySyncerSettings()),
        users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
        resolver=AsyncMock(),
        bot=mock_bot,
        dispatcher=mock_dispatcher,
        server_factory=mock_server_factory,
    )


class TestTelegramWebhookChannel:
    def test_dependencies_without_cloudflare(self, telegram_webhook_channel):
        deps = telegram_webhook_channel.dependencies
        assert telegram_webhook_channel._cloudflare_service is None
        assert mock_cloudflare_service not in deps

    def test_dependencies_with_cloudflare(
        self,
        telegram_webhook_settings_cloudflare,
        telegram_agent,
        mock_bot,
        mock_dispatcher,
        mock_cloudflare_service,
    ):
        channel = TelegramWebhookChannel(
            settings=telegram_webhook_settings_cloudflare,
            agent=telegram_agent,
            sessions_storage=MemorySessionsStorage(
                settings=MemorySessionsStorageSettings()
            ),
            syncer=MemorySyncer(settings=MemorySyncerSettings()),
            users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
            resolver=AsyncMock(),
            bot=mock_bot,
            dispatcher=mock_dispatcher,
            cloudflare_service=mock_cloudflare_service,
        )
        deps = channel.dependencies
        assert mock_cloudflare_service in deps

    @pytest.mark.asyncio
    async def test_listen_events_with_cloudflare(
        self,
        telegram_webhook_settings_cloudflare,
        telegram_agent,
        mock_bot,
        mock_dispatcher,
        mock_cloudflare_service,
        mock_server,
    ):
        channel = TelegramWebhookChannel(
            settings=telegram_webhook_settings_cloudflare,
            agent=telegram_agent,
            sessions_storage=MemorySessionsStorage(
                settings=MemorySessionsStorageSettings()
            ),
            syncer=MemorySyncer(settings=MemorySyncerSettings()),
            users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
            resolver=AsyncMock(),
            bot=mock_bot,
            dispatcher=mock_dispatcher,
            cloudflare_service=mock_cloudflare_service,
            server_factory=lambda config: mock_server,
        )
        await channel.listen_events()
        mock_cloudflare_service.get_public_url.assert_awaited()
        mock_bot.set_webhook.assert_awaited()
        mock_server.serve.assert_awaited()

    @pytest.mark.asyncio
    async def test_listen_events_without_cloudflare(
        self, telegram_webhook_channel, mock_bot, mock_server
    ):
        await telegram_webhook_channel.listen_events()
        mock_bot.set_webhook.assert_awaited()
        mock_server.serve.assert_awaited()

    @pytest.mark.asyncio
    async def test_listen_events_no_root_url_raises(
        self,
        telegram_webhook_settings,
        telegram_agent,
        mock_bot,
        mock_dispatcher,
    ):
        settings = telegram_webhook_settings.model_copy(update={"root_url": None})
        channel = TelegramWebhookChannel(
            settings=settings,
            agent=telegram_agent,
            sessions_storage=MemorySessionsStorage(
                settings=MemorySessionsStorageSettings()
            ),
            syncer=MemorySyncer(settings=MemorySyncerSettings()),
            users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
            resolver=AsyncMock(),
            bot=mock_bot,
            dispatcher=mock_dispatcher,
        )
        with pytest.raises(ValueError, match="root_url is required"):
            await channel.listen_events()

    def test_get_server_uses_factory(self, telegram_webhook_channel, mock_server):
        server = telegram_webhook_channel.get_server()
        assert server is mock_server

    def test_get_server_with_cloudflare_socket(
        self,
        telegram_webhook_settings_cloudflare,
        telegram_agent,
        mock_bot,
        mock_dispatcher,
        mock_cloudflare_service,
        mock_server,
    ):
        channel = TelegramWebhookChannel(
            settings=telegram_webhook_settings_cloudflare,
            agent=telegram_agent,
            sessions_storage=MemorySessionsStorage(
                settings=MemorySessionsStorageSettings()
            ),
            syncer=MemorySyncer(settings=MemorySyncerSettings()),
            users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
            resolver=AsyncMock(),
            bot=mock_bot,
            dispatcher=mock_dispatcher,
            cloudflare_service=mock_cloudflare_service,
            server_factory=lambda config: mock_server,
        )
        server = channel.get_server()
        assert server is mock_server

    @pytest.mark.asyncio
    async def test_handler_valid_secret(
        self, telegram_webhook_channel, mock_dispatcher
    ):
        update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1,
                "chat": {"id": 1, "type": "private"},
            },
        }
        await telegram_webhook_channel.handler(
            update=update,
            x_telegram_bot_api_secret_token="webhooksuperpupersecretaccesskey",
        )
        mock_dispatcher.feed_update.assert_awaited()

    @pytest.mark.asyncio
    async def test_handler_invalid_secret(self, telegram_webhook_channel):
        update = {"update_id": 1}
        with pytest.raises(Exception):
            await telegram_webhook_channel.handler(
                update=update,
                x_telegram_bot_api_secret_token="invalid",
            )

    @pytest.mark.asyncio
    async def test_handler_no_secret(self, telegram_webhook_channel):
        update = {"update_id": 1}
        with pytest.raises(Exception):
            await telegram_webhook_channel.handler(
                update=update, x_telegram_bot_api_secret_token=None
            )
