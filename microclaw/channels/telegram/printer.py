import uuid
from contextlib import asynccontextmanager

import aiogram

from microclaw.agents import Agent
from microclaw.channels.utils import AgentMessageHandler
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface


class AgentMessagePrinter(AgentMessageHandler):
    def __init__(
            self,
            user_message: aiogram.types.Message,
            session_id: uuid.UUID,
            sessions_storage: SessionsStorageInterface,
            agent: Agent,
            show_context_usage: bool = False,
            show_costs: bool = False,
            debug: bool = False,
    ):
        super().__init__()
        self._user_message = user_message
        self._session_id = session_id
        self._sessions_storage = sessions_storage
        self._agent = agent
        self._show_context_usage = show_context_usage
        self._show_costs = show_costs 
        self._debug = debug

        self._messages: list[AgentMessage] = []

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._flush_messages()

    async def handle_new_message(self, new_message: AgentMessage):
        if self.is_new_message_chunk:
            await self._flush_messages()
            self._messages.append(new_message)
        elif new_message.text:
            self._messages[-1].text += new_message.text
            
    async def _flush_messages(self):
        for message in self._messages:
            if not message.text:
                continue
            await self.print(text=message.text)
        self._messages = []

    @asynccontextmanager
    async def catch_exception(self):
        try:
            yield
        except Exception as exception:
            if self._debug:
                await self.print(text=f"Got exception: {exception}")
            else:
                await self.print(
                    text="Internal error, please contact agent administrator",
                )

    async def print(self, text: str):
        buttons = []
        if self._show_context_usage:
            actual_context_size = await self._sessions_storage.get_context_size(
                session_id=self._session_id,
            )
            model_context_size = self._agent.get_model_context_window_size()
            if model_context_size:
                context_usage = actual_context_size * 100 / model_context_size
                buttons.append(
                    aiogram.types.InlineKeyboardButton(
                        text=f"{context_usage:.2f}% context",
                        callback_data="null",
                    )
                )
        if self._show_costs:
            spending = await self._sessions_storage.get_spending(session_id=self._session_id)
            buttons.append(
                aiogram.types.InlineKeyboardButton(
                    text=f"{spending.cost:.4f} {spending.currency}",
                    callback_data="null",
                )
            )

        reply_markup = None
        if buttons:
            reply_markup = aiogram.types.InlineKeyboardMarkup(inline_keyboard=[buttons])

        text_list = [
            text[i:i + self.MAX_MESSAGE_LENGTH]
            for i in range(0, len(text), self.MAX_MESSAGE_LENGTH)
        ]
        
        for i, text_chunk in enumerate(text_list[:-1]):
            await self._user_message.answer(text=text_chunk)
        await self._user_message.answer(
            text=text_list[-1],
            reply_markup=reply_markup,
        )
