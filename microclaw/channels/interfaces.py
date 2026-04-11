import datetime
import uuid

import facet
from typing import Protocol

from microclaw.agents import Agent
from microclaw.dto import AgentMessage
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.toolkits import BaseToolKit
from microclaw.toolkits.memory.toolkit import MemorySizeExceeded
from .settings import ChannelSettings


class ChannelInterface(Protocol):
    def __init__(
            self,
            settings: ChannelSettings,
            agent: Agent,
            sessions_storage: SessionsStorageInterface,
            stt: STT | None = None,
            channel_key: str = "default",
    ):
        self._settings = settings
        self._agent = agent
        self._sessions_storage = sessions_storage
        self._stt = stt
        self._channel_key = channel_key

    def get_toolkit(self) -> BaseToolKit | None:
        return None

    @property
    def description(self) -> str | None:
        return self.__doc__

    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]:
        return []

    async def start(self):
        pass

    async def stop(self):
        pass

    async def run(self):
        raise NotImplementedError

    async def start_conversation(
            self,
            session_id: uuid.UUID,
            messages: list[AgentMessage] | None = None,
            **args,
    ):
        raise NotImplementedError

    async def summarize_dialog_if_needed(self, session_id: uuid.UUID) -> bool:
        if (
                not self._agent.is_summarization_enabled() or
                not await self.is_context_went_across_threshold(session_id=session_id)
        ):
            return False

        message_generator = self._sessions_storage.get_messages(
            session_id=session_id,
        )
        messages = [message async for message in message_generator]
        if not messages:
            return False

        if self._agent.is_memory_flush_enabled():
            memory_toolkit = self._agent.get_memory_toolkit()
            if memory_toolkit is not None:
                max_memory_flush_tokens = self._agent.get_max_memory_flush_tokens()
                general_info = await self._agent.extract_important_info(
                    messages=messages,
                    max_tokens=max_memory_flush_tokens,
                    is_daily=False,
                )
                if general_info:
                    await self._append_to_memory(content=general_info)

                daily_info = await self._agent.extract_important_info(
                    messages=messages,
                    max_tokens=max_memory_flush_tokens,
                    is_daily=True,
                )
                if daily_info:
                    await self._append_to_memory(content=daily_info, date=datetime.date.today())

        summary_message = await self._agent.summarize_dialogue(messages=messages)
        await self._sessions_storage.add_message(
            session_id=session_id,
            message=summary_message,
        )
        return True

    async def _append_to_memory(self, new_content: str, date: datetime.date | None = None):
        try:
            await memory_toolkit.append_to_memory(
                content=new_content,
                date=date,
            )
        except MemorySizeExceeded:
            old_content = await memory_toolkit.get_memory(date=date) or ""
            response = await self._agent.summarize_memory(
                old_context=old_content,
                new_context=new_content,
                is_daily=date is not None,
            )
            await memory_toolkit.rewrite_memory(
                content=response.content.strip(),
                date=date,
            )

    async def is_context_went_across_threshold(self, session_id: uuid.UUID) -> bool:
        context_window_size = self._agent.get_model_context_window_size()
        context_threshold = self._agent.get_context_threshold_size()
        if context_window_size is None or context_threshold is None:
            return False

        context_size = await self._sessions_storage.get_context_size(session_id=session_id)
        threshold_tokens = int(context_window_size * context_threshold)
        return context_size > threshold_tokens

    async def last_message_is_summary(self, session_id: uuid.UUID) -> bool:
        message = await self._sessions_storage.get_messages(
            session_id=session_id,
            last=1,
        )
        return message and message.is_summary
