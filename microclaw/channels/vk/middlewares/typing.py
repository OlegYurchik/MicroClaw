import asyncio

from loguru import logger
from vkbottle.bot import Message
from vkbottle.dispatch.middlewares.abc import BaseMiddleware


class VKTypingManager:
    def __init__(self, api, peer_id: int, group_id: int | None = None, delay: float = 3):
        self._api = api
        self._peer_id = peer_id
        self._group_id = group_id
        self._delay = delay
        self._background_task: asyncio.Task | None = None

    async def __aenter__(self):
        await self._stop_task()
        await self._start_task()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._stop_task()

    async def _resolve_group_id(self) -> int | None:
        if self._group_id is not None:
            return self._group_id

        try:
            response = await self._api.groups.get_by_id()
            if response.groups:
                self._group_id = response.groups[0].id
                return self._group_id
        except Exception:
            logger.warning("Failed to resolve VK group_id for typing activity")

        return None

    async def _start_task(self):
        if self._background_task is None:
            self._background_task = asyncio.create_task(self._run())

    async def _stop_task(self):
        if self._background_task is not None:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

    async def _run(self):
        group_id = await self._resolve_group_id()
        while True:
            try:
                await self._api.messages.set_activity(
                    group_id=group_id,
                    peer_id=self._peer_id,
                    type="typing",
                )
            except Exception:
                logger.debug("Failed to send VK typing activity")
            await asyncio.sleep(self._delay)


class VKTypingMiddleware(BaseMiddleware[Message]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._typing_manager: VKTypingManager | None = None

    async def pre(self) -> None:
        self._typing_manager = VKTypingManager(
            api=self.event.ctx_api,
            peer_id=self.event.peer_id,
            group_id=self.event.group_id,
        )
        await self._typing_manager._start_task()

    async def post(self) -> None:
        if self._typing_manager is not None:
            await self._typing_manager._stop_task()
            self._typing_manager = None
