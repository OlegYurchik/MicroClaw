import uuid

import facet
from typing import Protocol

from microclaw.agents import Agent
from microclaw.dto import AgentMessage
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.toolkits import BaseToolKit
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

        summary_message = await self._agent.summarize_dialog(messages=messages)
        await self._sessions_storage.add_message(
            session_id=session_id,
            message=summary_message,
        )
        return True

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
