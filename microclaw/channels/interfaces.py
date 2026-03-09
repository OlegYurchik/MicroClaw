import facet
from typing import Protocol

from microclaw.agents import Agent
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from .settings import ChannelSettings


class ChannelInterface(Protocol):
    def __init__(
            self,
            settings: ChannelSettings,
            agent: Agent,
            sessions_storage: SessionsStorageInterface,
            channel_key: str = "default",
    ):
        self._settings = settings
        self._agent = agent
        self._sessions_storage = sessions_storage
        self._channel_key = channel_key

    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]:
        return []

    async def start(self):
        pass

    async def stop(self):
        pass

    async def run(self):
        raise NotImplementedError

    async def summarize_dialog_if_needed(self) -> bool:
        if (
                not self._agent.is_summarization_enabled() or
                not await self.is_context_went_across_threshold()
        ):
            return False

        message_generator = self._sessions_storage.get_messages(
            session_id=self._session_id,
        )
        messages = [message async for message in message_generator]
        if not messages:
            return False

        summary_message = await self._agent.summarize_dialog(messages=messages)
        await self._sessions_storage.add_message(
            session_id=self._session_id,
            message=summary_message,
        )
        return True

    async def is_context_went_across_threshold(self) -> bool:
        context_window_size = self._agent.get_model_context_window_size()
        context_threshold = self._agent.get_context_threshold_size()
        if context_window_size is None or context_threshold is None:
            return False

        spending = await self._sessions_storage.get_spending(session_id=self._session_id)
        threshold_tokens = int(context_window_size * context_threshold)
        return spending.get_total_tokens() > threshold_tokens

    async def last_message_is_summary(self) -> bool:
        message = await self._sessions_storage.get_messages(
            session_id=self._session_id,
            last=1,
        )
        return message and message.is_summary
