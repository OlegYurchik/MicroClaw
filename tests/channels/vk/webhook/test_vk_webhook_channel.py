from unittest.mock import AsyncMock, MagicMock

from fastapi import Request
import pytest
import uvicorn

from microclaw.channels.vk.webhook.channel import VKWebhookChannel
from microclaw.channels.vk.webhook.settings import VKWebhookSettings
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def vk_webhook_settings() -> VKWebhookSettings:
    return VKWebhookSettings(
        token="vk_token",
        root_url="http://localhost:8080",
        root_path="/vk",
        secret_access_key="secret",
        title="Test",
        host="127.0.0.1",
        port=9000,
    )


@pytest.fixture
def mock_vk_bot() -> MagicMock:
    bot = MagicMock()
    bot.setup_webhook = AsyncMock(return_value=("code", "secret"))
    bot.callback = MagicMock()
    bot.callback.find_server_id = AsyncMock(return_value=None)
    bot.callback.set_callback_settings = AsyncMock()
    bot.process_event = AsyncMock()
    return bot


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
def vk_webhook_channel(
    vk_webhook_settings,
    telegram_agent,
    mock_vk_bot,
) -> VKWebhookChannel:
    channel = VKWebhookChannel(
        settings=vk_webhook_settings,
        agent=telegram_agent,
        sessions_storage=MemorySessionsStorage(
            settings=MemorySessionsStorageSettings()
        ),
        syncer=MemorySyncer(settings=MemorySyncerSettings()),
        users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
        resolver=AsyncMock(),
    )
    channel._bot = mock_vk_bot
    return channel


class TestVKWebhookChannel:
    def test_get_server_returns_uvicorn_server(self, vk_webhook_channel):
        server = vk_webhook_channel.get_server()
        assert isinstance(server, uvicorn.Server)

    @pytest.mark.asyncio
    async def test_handler_confirmation(self, vk_webhook_channel):
        vk_webhook_channel._confirmation_code = "test_code"
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value={"type": "confirmation"})
        response = await vk_webhook_channel._handler(request)
        assert response.body == b"test_code"

    @pytest.mark.asyncio
    async def test_handler_confirmation_not_ready(self, vk_webhook_channel):
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value={"type": "confirmation"})
        with pytest.raises(Exception) as exc_info:
            await vk_webhook_channel._handler(request)
        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_handler_invalid_secret(self, vk_webhook_channel):
        vk_webhook_channel._secret_access_key = "secret"
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value={"type": "message", "secret": "wrong"})
        with pytest.raises(Exception) as exc_info:
            await vk_webhook_channel._handler(request)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_handler_valid_secret(self, vk_webhook_channel, mock_vk_bot):
        vk_webhook_channel._secret_access_key = "secret"
        vk_webhook_channel.add_task = MagicMock()
        request = MagicMock(spec=Request)
        request.json = AsyncMock(
            return_value={"type": "message", "secret": "secret", "object": {}}
        )
        response = await vk_webhook_channel._handler(request)
        assert response.body == b"ok"
        mock_vk_bot.process_event.assert_called()

    @pytest.mark.asyncio
    async def test_handler_no_secret_check(self, vk_webhook_channel, mock_vk_bot):
        vk_webhook_channel._secret_access_key = None
        vk_webhook_channel.add_task = MagicMock()
        request = MagicMock(spec=Request)
        request.json = AsyncMock(return_value={"type": "message", "object": {}})
        response = await vk_webhook_channel._handler(request)
        assert response.body == b"ok"
        mock_vk_bot.process_event.assert_called()

    @pytest.mark.asyncio
    async def test_listen_events_no_root_url_raises(
        self,
        vk_webhook_settings,
        telegram_agent,
        mock_vk_bot,
    ):
        settings = vk_webhook_settings.model_copy(update={"root_url": None})
        channel = VKWebhookChannel(
            settings=settings,
            agent=telegram_agent,
            sessions_storage=MemorySessionsStorage(
                settings=MemorySessionsStorageSettings()
            ),
            syncer=MemorySyncer(settings=MemorySyncerSettings()),
            users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
            resolver=AsyncMock(),
        )
        channel._bot = mock_vk_bot
        with pytest.raises(ValueError, match="root_url is required"):
            await channel.listen_events()

    @pytest.mark.asyncio
    async def test_listen_events_flow(
        self, vk_webhook_channel, mock_vk_bot, mock_server
    ):
        vk_webhook_channel.get_server = lambda: mock_server
        await vk_webhook_channel.listen_events()
        mock_vk_bot.setup_webhook.assert_awaited()
        mock_server.serve.assert_awaited()

    @pytest.mark.asyncio
    async def test_listen_events_with_server_id(
        self, vk_webhook_channel, mock_vk_bot, mock_server
    ):
        vk_webhook_channel.get_server = lambda: mock_server
        mock_vk_bot.callback.find_server_id = AsyncMock(return_value=123)
        await vk_webhook_channel.listen_events()
        mock_vk_bot.callback.set_callback_settings.assert_awaited()
        mock_server.serve.assert_awaited()
