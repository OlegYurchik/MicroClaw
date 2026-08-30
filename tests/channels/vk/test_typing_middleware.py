from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.channels.vk.middlewares.typing import VKTypingMiddleware


class TestVKTypingMiddleware:
    @pytest.fixture
    def api(self):
        api = MagicMock()
        api.messages = MagicMock()
        api.messages.set_activity = AsyncMock()
        api.groups = MagicMock()
        api.groups.get_by_id = AsyncMock(
            return_value=MagicMock(groups=[MagicMock(id=42)])
        )
        return api

    def _make_middleware(self, api):
        event = MagicMock()
        event.ctx_api = api
        event.peer_id = 123
        event.group_id = 42
        middleware = VKTypingMiddleware(event)
        return middleware

    @pytest.mark.asyncio
    async def test_typing_middleware_sends_typing(self, api):
        middleware = self._make_middleware(api)
        await middleware.pre()
        assert middleware._typing_manager is not None
        import asyncio

        await asyncio.sleep(0.05)
        await middleware.post()

        api.messages.set_activity.assert_awaited()

    @pytest.mark.asyncio
    async def test_typing_middleware_ignores_errors(self, api):
        api.messages.set_activity.side_effect = RuntimeError("boom")
        middleware = self._make_middleware(api)
        await middleware.pre()
        assert middleware._typing_manager is not None
        # Let typing manager run briefly
        import asyncio

        await asyncio.sleep(0.05)
        await middleware.post()
        # should not raise
