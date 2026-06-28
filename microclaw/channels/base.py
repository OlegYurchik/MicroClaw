import asyncio
import contextlib
import contextvars
import datetime
import uuid

import facet
from typing import Self

from microclaw.agents import Agent, AgentSettings
from microclaw.dto import AgentMessage, User
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from microclaw.toolkits import BaseToolKit
from microclaw.toolkits.memory.toolkit import MemorySizeExceeded
from .settings import ChannelSettings


class ConfirmationMixin:
    CONFIRMATION_POLL_INTERVAL = 0.1

    async def request_confirmation(self, question: str) -> uuid.UUID:
        raise NotImplementedError

    async def resolve_confirmation(
            self,
            session_id: uuid.UUID,
            confirmation_id: uuid.UUID,
            approved: bool,
    ) -> None:
        await self._syncer.set(f"confirm:{session_id}:{confirmation_id}", approved)

    async def wait_for_confirmation(
            self,
            session_id: uuid.UUID,
            confirmation_id: uuid.UUID,
    ) -> bool:
        while True:
            result = await self._syncer.get(f"confirm:{session_id}:{confirmation_id}")
            if result is not None:
                await self._syncer.delete(f"confirm:{session_id}:{confirmation_id}")
                return result
            await asyncio.sleep(self.CONFIRMATION_POLL_INTERVAL)

    async def reject_all_pending_confirmations(self, session_id: uuid.UUID) -> None:
        pattern = f"confirm:{session_id}:*"
        keys = await self._syncer.scan_keys(pattern)
        for key in keys:
            await self._syncer.set(key, False)


class BaseChannel(facet.AsyncioServiceMixin, ConfirmationMixin):
    CHANNEL_CONTEXT = contextvars.ContextVar("channel_context", default=None)
    SESSION_ID_CONTEXT = contextvars.ContextVar("session_id", default=None)
    REQUEST_ID_CONTEXT = contextvars.ContextVar("request_id", default=None)

    def __init__(
            self,
            settings: ChannelSettings,
            agent: Agent,
            sessions_storage: SessionsStorageInterface,
            syncer: SyncerInterface,
            users_storage: UsersStorageInterface,
            resolver: "DependencyResolver",  # noqa: F821
            stt: STT | None = None,
            channel_key: str = "default",
    ):
        self._settings = settings
        self._agent = agent
        self._sessions_storage = sessions_storage
        self._stt = stt
        self._channel_key = channel_key
        self._syncer = syncer
        self._users_storage = users_storage
        self._resolver = resolver
        self._user_agents_cache: dict[uuid.UUID, Agent] = {}

    @property
    def description(self) -> str | None:
        return self.__doc__
    
    def get_toolkit(self) -> BaseToolKit | None:
        return None
    
    def get_sessions_storage(self) -> SessionsStorageInterface:
        return self._sessions_storage
    
    def get_users_storage(self) -> UsersStorageInterface:
        return self._users_storage

    @classmethod
    def get_current_channel(cls) -> Self:
        return cls.CHANNEL_CONTEXT.get(None)

    @contextlib.contextmanager
    def set_current_channel(self):
        token = self.CHANNEL_CONTEXT.set(self)
        try:
            yield
        finally:
            self.CHANNEL_CONTEXT.reset(token)

    @contextlib.contextmanager
    def set_current_request_id(self, request_id: uuid.UUID):
        token = self.REQUEST_ID_CONTEXT.set(request_id)
        try:
            yield
        finally:
            self.REQUEST_ID_CONTEXT.reset(token)

    @classmethod
    def get_current_request_id(cls) -> uuid.UUID | None:
        return cls.REQUEST_ID_CONTEXT.get(None)

    @classmethod
    def get_current_session_id(cls) -> uuid.UUID | None:
        return cls.SESSION_ID_CONTEXT.get(None)

    @contextlib.contextmanager
    def set_current_session_id(self, session_id: uuid.UUID):
        token = self.SESSION_ID_CONTEXT.set(session_id)
        try:
            yield
        finally:
            self.SESSION_ID_CONTEXT.reset(token)

    async def get_agent_for_user(self, user: User) -> Agent | None:
        if user.agent is None:
            return None
        if user.id in self._user_agents_cache:
            return self._user_agents_cache[user.id]

        agent_settings = AgentSettings(**user.agent)
        agent = await self._resolver.resolve_agent(agent_settings=agent_settings)
        self._user_agents_cache[user.id] = agent
        return agent

    async def start_conversation(
            self,
            session_id: uuid.UUID,
            channel_internal_id: int,
            new_messages: list[AgentMessage] | None = None,
            agent: Agent | None = None,
    ):
        raise NotImplementedError

    async def summarize_dialog_if_needed(
            self,
            agent: Agent,
            session_id: uuid.UUID,
    ) -> bool:
        if (
                not agent.is_summarization_enabled() or
                not await self.is_context_went_across_threshold(
                    agent=agent,
                    session_id=session_id,
                )
        ):
            return False

        message_generator = self._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_id),
        )
        messages = [message async for message in message_generator]
        if not messages:
            return False

        if agent.is_memory_flush_enabled():
            memory_toolkit = agent.get_memory_toolkit()
            if memory_toolkit is not None:
                max_memory_flush_tokens = agent.get_max_memory_flush_tokens()
                general_info = await agent.extract_important_info(
                    messages=messages,
                    max_tokens=max_memory_flush_tokens,
                    is_daily=False,
                )
                if general_info:
                    await self._append_to_memory(agent=agent, new_content=general_info)

                daily_info = await agent.extract_important_info(
                    messages=messages,
                    max_tokens=max_memory_flush_tokens,
                    is_daily=True,
                )
                if daily_info:
                    await self._append_to_memory(
                        agent=agent,
                        new_content=daily_info,
                        date=datetime.date.today(),
                    )

        summary_message = await agent.summarize_dialogue(messages=messages)
        await self._sessions_storage.add_message(
            session_id=session_id,
            message=summary_message,
        )
        return True

    async def is_context_went_across_threshold(
            self,
            agent: Agent,
            session_id: uuid.UUID,
    ) -> bool:
        context_window_size = agent.get_model_context_window_size()
        context_threshold = agent.get_context_threshold_size()
        if context_window_size is None or context_threshold is None:
            return False

        context_size = await self._sessions_storage.get_context_size(session_id=session_id)
        threshold_tokens = int(context_window_size * context_threshold)
        return context_size > threshold_tokens

    async def _append_to_memory(
            self,
            agent: Agent,
            new_content: str,
            date: datetime.date | None = None,
    ):
        memory_toolkit = agent.get_memory_toolkit()
        try:
            await memory_toolkit.append_to_memory(
                content=new_content,
                date=date,
            )
        except MemorySizeExceeded:
            old_content = await memory_toolkit.get_memory(date=date) or ""
            response = await agent.summarize_memory(
                old_context=old_content,
                new_context=new_content,
                is_daily=date is not None,
            )
            await memory_toolkit.rewrite_memory(
                content=response.content.strip(),
                date=date,
            )
