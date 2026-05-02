import asyncio
from typing import Any

import aiogram
import fastapi
import uvicorn
import yarl

from microclaw.channels.telegram.base import BaseTelegramChannel


class UvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass


class TelegramWebhookChannel(BaseTelegramChannel):
    async def listen_events(self):
        webhook_url = yarl.URL(str(self._settings.root_url)) / self._settings.root_path.lstrip("/")
        await self._bot.set_webhook(
            url=str(webhook_url),
            secret_token=self._settings.secret_access_key,
        )
        
        await self.get_server().serve()

    def get_server(self) -> uvicorn.Server:
        app = fastapi.FastAPI(
            root_url=self._settings.root_url,
            root_path=self._settings.root_path,
        )
        app.post("")(self.handler)

        config = uvicorn.Config(app=app, host="0.0.0.0", port=self._settings.port)
        return UvicornServer(config)

    async def handler(
            self,
            update: dict[str, Any],
            x_telegram_bot_api_secret_token: str | None = fastapi.Header(None),
    ):
        if x_telegram_bot_api_secret_token != self._settings.secret_access_key:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_403_FORBIDDEN,
                detail="Forbidden.",
            )

        telegram_update = aiogram.types.Update(**update)
        await self._dispatcher.feed_update(bot=self._bot, update=telegram_update)