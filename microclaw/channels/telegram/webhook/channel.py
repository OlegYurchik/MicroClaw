import errno
import os
import tempfile
from typing import Any

import aiogram
import facet
import fastapi
import uvicorn
import yarl

from microclaw.channels.telegram.base import BaseTelegramChannel
from .cloudflare import CloudflareTunnelService


class UvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass


class TelegramWebhookChannel(BaseTelegramChannel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._socket_path: str | None = None
        self._cloudflare_service: CloudflareTunnelService | None = None
        
        if self._settings.cloudflare.enabled:
            temp_dir = tempfile.gettempdir()
            self._socket_path = os.path.join(temp_dir, f"fcgi-socket-{os.getpid()}.sock")
            
            local_url = f"http+unix://{self._socket_path}"
            
            self._cloudflare_service = CloudflareTunnelService(
                settings=self._settings.cloudflare,
                local_url=local_url,
                port=self._settings.port,
            )

    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]:
        dependencies = super().dependencies
        
        if self._cloudflare_service:
            dependencies.append(self._cloudflare_service)

        return dependencies

    async def listen_events(self):
        if self._cloudflare_service:
            base_url = yarl.URL(await self._cloudflare_service.get_public_url())
        else:
            if not self._settings.root_url:
                raise ValueError("root_url is required when cloudflare is disabled")
            base_url = yarl.URL(str(self._settings.root_url))
        
        webhook_url = base_url / self._settings.root_path.lstrip("/")
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
        app.post("/")(self.handler)

        if self._settings.cloudflare.enabled and self._socket_path:
            self._ensure_socket_cleanup()
            config = uvicorn.Config(app=app, uds=self._socket_path)
        else:
            config = uvicorn.Config(app=app, host="0.0.0.0", port=self._settings.port)
        
        return UvicornServer(config)
    
    def _ensure_socket_cleanup(self):
        if self._socket_path and os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

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
