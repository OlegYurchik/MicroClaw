from typing import Awaitable, Callable, Iterable

import aiogram


class AuthMiddleware(aiogram.BaseMiddleware):
    def __init__(self, allow_from: Iterable[str]):
        super().__init__()
        self._allow_from = set(allow_from)
    
    async def __call__(
            self,
            handler: Callable,
            event: aiogram.types.Message,
            data: dict,
    ) -> Awaitable:
        if self._allow_from:
            user_set = {event.from_user.id, str(event.from_user.id), event.from_user.username}
            is_allowed = user_set & self._allow_from
            if not is_allowed:
                return

        return await handler(event, data) 
