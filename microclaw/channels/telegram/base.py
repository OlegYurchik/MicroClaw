import asyncio
from contextlib import asynccontextmanager
from typing import Coroutine

import aiogram
import facet

from microclaw.agents import Agent
from microclaw.channels.interfaces import ChannelInterface
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface
from .settings import TelegramSettings


@asynccontextmanager
async def background_task(coroutine: Coroutine):
    task = asyncio.create_task(coroutine)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class BaseTelegramChannel(facet.AsyncioServiceMixin, ChannelInterface):
    END_PHRASE = "NO_REPLY"
    TYPING_ACTION_DELAY = 3

    def __init__(
            self,
            settings: TelegramSettings,
            agent: Agent,
            sessions_storage: SessionsStorageInterface,
            channel_key: str = "default",
    ):
        super().__init__(
            settings=settings,
            agent=agent,
            sessions_storage=sessions_storage,
            channel_key=channel_key,
        )
        self._bot = aiogram.Bot(token=settings.token)
        self._dispatcher = aiogram.Dispatcher()
        self._dispatcher.message()(self.handle_message)

    async def start(self):
        self.add_task(self.listen_events())

    async def listen_events(self):
        raise NotImplementedError

    async def handle_message(self, message: aiogram.types.Message):
        if self._settings.allow_from is not None:
            user_id = message.from_user.id
            username = message.from_user.username
            user_set = {message.from_user.id, str(message.from_user.id), message.from_user.username}
            is_allowed = user_set & set(self._settings.allow_from)
            if not is_allowed:
                return

        session_id = f"telegram:{self._channel_key}:{message.chat.id}:{message.from_user.id}"

        await self._sessions_storage.add_message(
            session_id=session_id,
            message=AgentMessage(role="user", content=message.text),
        )
        message_generator = self._sessions_storage.get_messages(session_id=session_id)
        messages = [message async for message in message_generator]

        messages_queue = []
        last_chunked_message_id = None
        typing_coroutine = self._send_typing_action_background(message=message)
        async with background_task(typing_coroutine):
            async for new_message in self._agent.ask(messages=messages):
                is_new_chunk = (
                    new_message.chunked_message_id is None or
                    new_message.chunked_message_id != last_chunked_message_id
                )

                if is_new_chunk:
                    if messages_queue and messages_queue[-1].role == "assistant" and messages_queue[-1].content:
                        await message.answer(messages_queue[-1].content)
                    messages_queue.append(new_message)
                else:
                    messages_queue[-1].content += new_message.content

                last_chunked_message_id = new_message.chunked_message_id
        if messages_queue and messages_queue[-1].role == "assistant" and messages_queue[-1].content:
            await message.answer(messages_queue[-1].content)

        for msg in messages_queue:
            await self._sessions_storage.add_message(
                session_id=session_id,
                message=msg,
            )
        
        await self._check_context_threshold(session_id=session_id, chat_id=message.chat.id)

    async def handle_reset_command(self, message: aiogram.types.Message):
        raise NotImplementedError

    async def _send_typing_action_background(self, message: aiogram.types.Message):
        while True:
            await message.bot.send_chat_action(
                chat_id=message.chat.id,
                action="typing",
            )
            await asyncio.sleep(self.TYPING_ACTION_DELAY)
