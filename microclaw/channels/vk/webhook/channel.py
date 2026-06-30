import asyncio

import fastapi
import uvicorn
from fastapi import Request
from fastapi.responses import PlainTextResponse
from vkbottle.callback import BotCallback
from vkbottle.bot import Bot
from vkbottle_types.events import GroupEventType

from microclaw.channels.vk.base import BaseVKChannel


class UvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass


class VKWebhookChannel(BaseVKChannel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._confirmation_code: str | None = None
        self._secret_access_key: str | None = None

        self._callback = BotCallback(
            url=str(self._settings.root_url),
            title=self._settings.title,
            secret_key=self._settings.secret_access_key,
        )

        self._bot = Bot(
            token=self._settings.token,
            callback=self._callback,
        )
        self._bot.on.message()(self._handle_message)
        self._bot.on.raw_event(
            GroupEventType.MESSAGE_EVENT,
            dataclass=dict,
        )(self._handle_confirmation_callback)

    async def listen_events(self):
        if not self._settings.root_url:
            raise ValueError("root_url is required for vk webhook")

        server = self.get_server()
        server_task = asyncio.create_task(server.serve())

        # Give uvicorn a moment to start listening before calling setup_webhook
        await asyncio.sleep(1)

        self._confirmation_code, self._secret_access_key = await self._bot.setup_webhook()

        await server_task

    def get_server(self) -> uvicorn.Server:
        app = fastapi.FastAPI(
            root_url=self._settings.root_url,
            root_path=self._settings.root_path,
        )
        app.post("/")(self._handler)

        config = uvicorn.Config(
            app=app,
            host=self._settings.host,
            port=self._settings.port,
        )
        return UvicornServer(config)

    async def _handler(self, request: Request):
        data = await request.json()
        event_type = data.get("type")

        if event_type == "confirmation":
            if not self._confirmation_code:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Webhook not configured yet.",
                )
            return PlainTextResponse(self._confirmation_code)

        if self._secret_access_key:
            if data.get("secret") != self._secret_access_key:
                raise fastapi.HTTPException(
                    status_code=fastapi.status.HTTP_403_FORBIDDEN,
                    detail="Forbidden.",
                )

        await self._bot.process_event(data)
        return PlainTextResponse("ok")
