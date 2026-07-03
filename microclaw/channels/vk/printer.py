import random
import uuid

from vkbottle.bot import Bot

from microclaw.agents import Agent
from microclaw.channels.utils import AgentMessageCollector
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface


class VKAgentMessagePrinter(AgentMessageCollector):
    MAX_MESSAGE_LENGTH = 4096

    def __init__(
            self,
            bot: Bot,
            peer_id: int,
            session_id: uuid.UUID,
            sessions_storage: SessionsStorageInterface,
            agent: Agent,
            show_context_usage: bool = False,
            show_costs: bool = False,
            debug: bool = False,
    ):
        super().__init__()
        self._bot = bot
        self._peer_id = peer_id
        self._session_id = session_id
        self._sessions_storage = sessions_storage
        self._agent = agent
        self._show_context_usage = show_context_usage
        self._show_costs = show_costs
        self._debug = debug

        self._messages: list[AgentMessage] = []

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self._flush_messages()
        if exc_type is not None:
            if self._debug:
                await self.print(text=f"Got exception: {exc_val}")
            else:
                await self.print(
                    text="Internal error, please contact agent administrator",
                )
        await super().__aexit__(exc_type, exc_val, exc_tb)
        return True

    async def handle_new_message(self, new_message: AgentMessage):
        if new_message.role != "assistant" or not new_message.text:
            return

        if self.is_new_message_chunk:
            await self._flush_messages()
            self._messages.append(new_message.model_copy())
        elif new_message.text:
            self._messages[-1].text += new_message.text

    async def _flush_messages(self):
        for message in self._messages:
            if not message.text:
                continue
            await self.print(text=message.text)
        self._messages = []

    async def print(self, text: str):
        text_chunks = [
            text[i:i + self.MAX_MESSAGE_LENGTH].strip()
            for i in range(0, len(text), self.MAX_MESSAGE_LENGTH)
        ]

        for chunk in text_chunks:
            if not chunk:
                continue
            await self._bot.api.messages.send(
                peer_id=self._peer_id,
                message=chunk,
                random_id=random.randint(-2147483648, 2147483647),
            )
