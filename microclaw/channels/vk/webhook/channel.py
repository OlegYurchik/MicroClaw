import asyncio

from aiohttp import ClientError
import fastapi
from fastapi import Request
from fastapi.responses import PlainTextResponse
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
import uvicorn
from vkbottle.bot import Bot
from vkbottle.callback import BotCallback
from vkbottle.exception_factory import VKAPIError

from microclaw.channels.vk.base import BaseVKChannel


class UvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass


class VKWebhookChannel(BaseVKChannel):
    def __init__(self, *args, **kwargs):
        self._confirmation_code: str | None = None
        self._secret_access_key: str | None = None
        super().__init__(*args, **kwargs)

    def _create_bot(self) -> Bot:
        self._callback = BotCallback(
            url=str(self._settings.root_url),
            title=self._settings.title,
            secret_key=self._settings.secret_access_key,
        )
        return Bot(
            token=self._settings.token,
            callback=self._callback,
        )

    async def listen_events(self):
        if not self._settings.root_url:
            raise ValueError("root_url is required for vk webhook")

        server = self.get_server()
        server_task = asyncio.create_task(server.serve())

        await asyncio.sleep(1)

        _setup_webhook = retry(
            retry=retry_if_exception_type((ClientError, VKAPIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.setup_webhook)

        (
            self._confirmation_code,
            self._secret_access_key,
        ) = await _setup_webhook()

        _find_server_id = retry(
            retry=retry_if_exception_type((ClientError, VKAPIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.callback.find_server_id)

        server_id = await _find_server_id()
        if server_id is not None:
            _set_callback_settings = retry(
                retry=retry_if_exception_type((ClientError, VKAPIError)),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            )(self._bot.callback.set_callback_settings)

            await _set_callback_settings(
                server_id,
                {"message_event": True},
            )

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

        self.add_task(self._bot.process_event(data))
        return PlainTextResponse("ok")
