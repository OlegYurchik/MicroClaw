from unittest.mock import AsyncMock, MagicMock

import aiogram
import pytest

from microclaw.channels.telegram.middlewares.auth import AuthMiddleware


class TestAuthMiddleware:
    @pytest.fixture
    def handler(self):
        return AsyncMock()

    @pytest.fixture
    def make_event(self):
        def _make(user_id=123, username="testuser"):
            event = MagicMock(spec=aiogram.types.Message)
            from_user = MagicMock()
            from_user.id = user_id
            from_user.username = username
            event.from_user = from_user
            return event

        return _make

    @pytest.mark.asyncio
    async def test_auth_allowed_user_by_id(self, handler, make_event):
        middleware = AuthMiddleware(allow_from=["123"])
        event = make_event(user_id=123)
        await middleware(handler, event, {})
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_allowed_user_by_username(self, handler, make_event):
        middleware = AuthMiddleware(allow_from=["testuser"])
        event = make_event(username="testuser")
        await middleware(handler, event, {})
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_denied_user(self, handler, make_event):
        middleware = AuthMiddleware(allow_from=["999"])
        event = make_event(user_id=123)
        result = await middleware(handler, event, {})
        handler.assert_not_awaited()
        assert result is None

    @pytest.mark.asyncio
    async def test_auth_no_allow_from(self, handler, make_event):
        middleware = AuthMiddleware(allow_from=[])
        event = make_event(user_id=123)
        await middleware(handler, event, {})
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_str_id_matching(self, handler, make_event):
        middleware = AuthMiddleware(allow_from=["123"])
        event = make_event(user_id=123)
        await middleware(handler, event, {})
        handler.assert_awaited_once()
