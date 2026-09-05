from collections.abc import Sequence
import contextlib
import dataclasses
import datetime
import json
import uuid

from .settings import ChannelSettings
import facet
from loguru import logger

from microclaw.agents import Agent, AgentSettings
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage, DecisionEnum, User
from microclaw.sessions_storages.dto import MessageCreate, SessionCreate
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.toolkits import BaseToolKit
from microclaw.toolkits.accessors import (
    AllSessionsAccessor,
    AllUsersAccessor,
    CurrentSessionAccessor,
    CurrentUserAccessor,
    UserSessionsAccessor,
)
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.dto import DiscoveryInfo
from microclaw.toolkits.memory.toolkit import MemorySizeExceeded
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.dto import (
    UserChannelCreate,
    UserChannelUpdate,
    UserCreate,
)
from microclaw.users_storages.exceptions import AlreadyExistsError
from microclaw.users_storages.filters import UserChannelFilter, UserFilter
from microclaw.utils.context import (
    get_current_request_id,
    set_current_request_id,
    set_current_session_id,
)


class BaseChannel(facet.AsyncioServiceMixin):
    CHAT_LOCK_TTL_SECONDS = 300
    CHAT_LOCK_WAIT_TIMEOUT = 300
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

    async def start_conversation(
        self,
        channel_internal_id: int,
        session_id: uuid.UUID,
        new_messages: list[AgentMessage] | None = None,
        agent: Agent | None = None,
    ):
        chat_id = channel_internal_id
        request_id = uuid.uuid4()
        with set_current_request_id(request_id):
            user = await self._get_or_create_user(chat_id)
            agent = agent or await self.get_agent_for_user(user) or self._agent
            await self._enqueue_and_process(
                chat_id=chat_id,
                session_id=session_id,
                new_messages=new_messages or [],
                agent=agent,
            )

    async def handle_new_session(self, chat_id: str | int) -> None:
        async with self._lock_chat_for_processing(chat_id):
            queue_key = self._get_chat_queue_key(chat_id)
            await self._syncer.list_pop_all(queue_key)
            user = await self._get_or_create_user(chat_id)
            await self._create_new_session(user, chat_id)
            await self._send_system_message(chat_id, "Dialog context reset")


    async def _enqueue_and_process(
        self,
        chat_id: str | int,
        new_messages: Sequence[AgentMessage],
        agent: Agent,
        session_id: uuid.UUID | None = None,
        stream: bool = False,
    ) -> None:
        queue_key = self._get_chat_queue_key(chat_id)
        for message in new_messages:
            await self._syncer.list_append(
                queue_key, message.model_dump(mode="json")
            )

        lock_key = self._get_chat_processing_lock_key(chat_id)
        has_lock = await self._syncer.set_if_not_exists(
            lock_key, True, ttl=self.CHAT_LOCK_TTL_SECONDS
        )
        if not has_lock:
            await self._on_message_queued(chat_id)
            while not await self._syncer.set_if_not_exists(
                lock_key, True, ttl=self.CHAT_LOCK_TTL_SECONDS
            ):
                await self._syncer.wait_delete(
                    lock_key, timeout=self.CHAT_LOCK_WAIT_TIMEOUT
                )

        try:
            while True:
                raw_batch = await self._syncer.list_pop_all(queue_key)
                if not raw_batch:
                    break

                batch: list[AgentMessage] = []
                for raw in raw_batch:
                    try:
                        batch.append(AgentMessage(**raw))
                    except Exception:
                        logger.exception(
                            "Failed to deserialize queued message for chat {}, skipping",
                            chat_id,
                        )
                        continue

                if not batch:
                    continue

                resolved_session_id = (
                    session_id if session_id is not None
                    else await self._resolve_session_for_chat(chat_id)
                )
                session_id = None

                for message in batch:
                    await self._sessions_storage.create_message(
                        data=MessageCreate(
                            session_id=resolved_session_id,
                            message=message,
                        )
                    )

                batch_kwargs = {
                    "chat_id": chat_id,
                    "session_id": resolved_session_id,
                    "agent": agent,
                    "batch": batch,
                }
                if "stream" in self._process_batch.__code__.co_varnames:
                    batch_kwargs["stream"] = stream
                await self._process_batch(**batch_kwargs)
        finally:
            await self._syncer.delete(lock_key)

    async def _on_message_queued(self, chat_id: str | int) -> None:
        """Called when a message is queued but processing is delayed because another batch is in progress."""

    async def _process_batch(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        batch: Sequence[AgentMessage],
        decision: DecisionEnum | None = None,
        stream: bool = False,
    ) -> None:
        request_id = get_current_request_id() or uuid.uuid4()
        saver = AgentMessageSaver(
            sessions_storage=self._sessions_storage,
            session_id=session_id,
        )

        message_generator = self._sessions_storage.get_messages(
            filter_=MessageFilter(session_id={session_id})
        )
        history = [m async for m in message_generator]

        user = await self._get_or_create_user(chat_id)

        async with self._on_processing(chat_id, session_id, agent):
            with (
                self.set_toolkit_context(
                    session_id=session_id,
                    request_id=request_id,
                    channel_internal_id=str(chat_id),
                    user=user,
                    agent=agent,
                ),
                set_current_session_id(session_id),
            ):
                async with saver:
                    has_interrupt = await agent.has_pending_interrupt(
                        session_id=session_id
                    )
                    if decision is not None or has_interrupt:
                        msg_generator = agent.resume_after_confirmation(
                            session_id=session_id,
                            decision=decision or DecisionEnum.REJECT,
                            new_messages=batch,
                            channel=self,
                        )
                    else:
                        msg_generator = agent.ask(messages=history, channel=self, stream=stream)

                    async for new_message in msg_generator:
                        await saver.register_new_message(new_message)
                        if new_message.role == "request_confirmation":
                            entries = json.loads(new_message.text)
                            await self._on_confirmation_request(
                                chat_id, session_id, agent, entries
                            )
                        else:
                            await self._on_agent_message(
                                chat_id, session_id, agent, new_message
                            )

            if (
                await self.summarize_dialog_if_needed(
                    agent=agent, session_id=session_id
                )
                and self._settings.debug
            ):
                await self._send_system_message(chat_id, "Dialog summarized")

            logger.info(
                "[{}] Finished generation for session_id={} chat_id={}",
                request_id, session_id, chat_id,
            )

    @contextlib.asynccontextmanager
    async def _on_processing(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
    ):
        """Async context manager that wraps a single processing batch.

        Channels may override this to allocate and clean up resources tied to
        the processing lifecycle (e.g. message printers, progress trackers).
        The default implementation is a no-op.
        """
        yield

    async def _on_agent_message(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        msg: AgentMessage,
    ) -> None:
        """Called for each message yielded by the agent during processing."""

    async def _on_confirmation_request(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        entries: list[dict],
    ) -> None:
        """Called when the agent requests user confirmation for tool calls."""

    async def _send_system_message(self, chat_id: str | int, text: str) -> None:
        """Override to send simple system messages (e.g. reset confirmation, errors, debug)."""

    def set_agent(self, agent: Agent) -> None:
        self._agent = agent
        self._user_agents_cache.clear()

    async def get_agent_for_user(self, user: User) -> Agent | None:
        if user.agent is None:
            return None
        if user.id in self._user_agents_cache:
            return self._user_agents_cache[user.id]

        agent_settings = AgentSettings(**user.agent)
        agent = await self._resolver.resolve_agent(
            agent_settings=agent_settings,
            user_id=user.id,
        )
        self._user_agents_cache[user.id] = agent
        return agent

    async def _resolve_session_for_chat(self, chat_id: str | int) -> uuid.UUID:
        user = await self._get_or_create_user(chat_id)
        return await self._get_or_create_session(user, chat_id)

    async def _get_or_create_user(self, chat_id: str | int) -> User:
        channel = await self._users_storage.get_user_channel(
            filter_=UserChannelFilter(
                channel_key={self._channel_key},
                channel_internal_id={str(chat_id)},
            )
        )
        if channel is not None:
            user = await self._users_storage.get_user(
                filter_=UserFilter(id={channel.user_id})
            )
            if user is not None:
                return user
        return await self._users_storage.create_user(data=UserCreate())

    async def _get_or_create_session(
        self, user: User, chat_id: str | int
    ) -> uuid.UUID:
        channel = await self._users_storage.get_user_channel(
            filter_=UserChannelFilter(
                user_id={user.id},
                channel_key={self._channel_key},
                channel_internal_id={str(chat_id)},
            )
        )
        if channel is not None and channel.actual_session_id is not None:
            return channel.actual_session_id
        return await self._create_new_session(user, chat_id)

    async def _create_new_session(
        self, user: User, chat_id: str | int
    ) -> uuid.UUID:
        session_id = uuid.uuid4()
        await self._sessions_storage.create_session(
            data=SessionCreate(
                id=session_id,
                channel_key=self._channel_key,
                channel_internal_id=str(chat_id),
            )
        )
        try:
            await self._users_storage.create_user_channel(
                data=UserChannelCreate(
                    user_id=user.id,
                    channel_key=self._channel_key,
                    channel_internal_id=str(chat_id),
                    actual_session_id=session_id,
                )
            )
        except AlreadyExistsError:
            async for _ in self._users_storage.update_user_channels(
                filter_=UserChannelFilter(
                    user_id={user.id},
                    channel_key={self._channel_key},
                    channel_internal_id={str(chat_id)},
                ),
                data=UserChannelUpdate(actual_session_id=session_id),
            ):
                pass
        return session_id

    async def summarize_dialog_if_needed(
        self,
        agent: Agent,
        session_id: uuid.UUID,
    ) -> bool:
        if (
            not agent.is_summarization_enabled()
            or not await self.is_context_went_across_threshold(
                agent=agent,
                session_id=session_id,
            )
        ):
            return False

        message_generator = self._sessions_storage.get_messages(
            filter_=MessageFilter(session_id={session_id}),
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
        await self._sessions_storage.create_message(
            data=MessageCreate(
                session_id=session_id,
                message=summary_message,
            )
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

        session = await self._sessions_storage.get_session(
            filter_=SessionFilter(id={session_id})
        )
        context_size = session.context_size if session else 0
        threshold_tokens = int(context_window_size * context_threshold)
        return context_size > threshold_tokens

    async def _append_to_memory(
        self,
        agent: Agent,
        new_content: str,
        date: datetime.date | None = None,
    ):
        memory_toolkit = agent.get_memory_toolkit()
        if memory_toolkit is None:
            return
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
        except Exception:
            logger.exception("Failed to append to memory")

    @contextlib.contextmanager
    def set_toolkit_context(
        self,
        session_id: uuid.UUID,
        request_id: uuid.UUID,
        channel_internal_id: str,
        user: User,
        agent: Agent,
    ):
        needed_caps, discovery_caps, write_caps = self._collect_capabilities(agent)

        context = ToolkitExecutionContext(
            session_id=session_id,
            request_id=request_id,
            channel_key=self._channel_key,
            channel_internal_id=channel_internal_id,
        )

        context = self._build_accessors_context(
            context, agent, user, needed_caps, write_caps
        )
        context = self._build_discovery_context(context, agent, discovery_caps)

        token = TOOLKIT_CONTEXT.set(context)
        try:
            yield
        finally:
            TOOLKIT_CONTEXT.reset(token)

    def _collect_capabilities(self, agent: Agent) -> tuple[set, set, set]:
        needed_caps = set()
        discovery_caps = set()
        write_caps = set()
        for toolkit in agent.toolkits.values():
            needed_caps.update(toolkit.required_capabilities)
            discovery_caps.update(toolkit.discovery_capabilities)
            write_caps.update(toolkit.write_capabilities)
        return needed_caps, discovery_caps, write_caps

    def _build_accessors_context(
        self,
        context: ToolkitExecutionContext,
        agent: Agent,
        user: User,
        needed_caps: set,
        write_caps: set,
    ) -> ToolkitExecutionContext:
        if ToolKitCapability.CURRENT_USER in needed_caps:
            context = dataclasses.replace(
                context,
                current_user_accessor=CurrentUserAccessor(
                    user_id=user.id,
                    storage=self._users_storage,
                    writable=(ToolKitCapability.CURRENT_USER in write_caps),
                    invalidate_cache=(
                        lambda: self._user_agents_cache.pop(user.id, None)
                        if ToolKitCapability.CURRENT_USER in write_caps
                        else None
                    ),
                ),
            )

        if ToolKitCapability.ALL_USERS in needed_caps:
            context = dataclasses.replace(
                context,
                all_users_accessor=AllUsersAccessor(storage=self._users_storage),
            )

        if ToolKitCapability.CURRENT_USER in needed_caps:
            context = dataclasses.replace(
                context,
                user_sessions_accessor=UserSessionsAccessor(
                    user_id=user.id,
                    storage=self._users_storage,
                ),
            )

        if ToolKitCapability.CURRENT_SESSION in needed_caps:
            context = dataclasses.replace(
                context,
                current_session_accessor=CurrentSessionAccessor(
                    session_id=context.session_id,
                    storage=self._sessions_storage,
                    writable=(ToolKitCapability.CURRENT_SESSION in write_caps),
                ),
            )

        if ToolKitCapability.ALL_SESSIONS in needed_caps:
            context = dataclasses.replace(
                context,
                sessions_accessor=AllSessionsAccessor(storage=self._sessions_storage),
            )

        return context

    def _build_discovery_context(
        self,
        context: ToolkitExecutionContext,
        agent: Agent,
        discovery_caps: set,
    ) -> ToolkitExecutionContext:
        if DiscoveryCapability.MODELS in discovery_caps:
            context = dataclasses.replace(
                context,
                all_models={k: DiscoveryInfo(name=k) for k in self._resolver.settings.models},
            )

        if DiscoveryCapability.TOOLKITS in discovery_caps:
            context = dataclasses.replace(
                context,
                all_toolkits={
                    k: DiscoveryInfo(name=k, description=v.prompt)
                    for k, v in self._resolver.settings.toolkits.items()
                },
            )

        if DiscoveryCapability.SKILLS in discovery_caps:
            context = dataclasses.replace(
                context,
                all_skills={
                    k: DiscoveryInfo(name=(v if isinstance(v, str) else v.name))
                    for k, v in self._resolver.settings.skills.items()
                },
            )

        if DiscoveryCapability.AGENTS in discovery_caps:
            current_agent_name = agent.name
            context = dataclasses.replace(
                context,
                all_agents={
                    k: DiscoveryInfo(
                        name=v.identity.name if v.identity else k,
                        description=v.identity.description if v.identity else None,
                    )
                    for k, v in self._resolver.settings.agents.items()
                    if k != current_agent_name
                },
            )

        if DiscoveryCapability.MCP in discovery_caps:
            context = dataclasses.replace(
                context,
                all_mcp={
                    k: DiscoveryInfo(
                        name=(v.name or k),
                        description=v.description,
                    )
                    for k, v in self._resolver.settings.mcp.items()
                },
            )

        return context

    def _get_channel_type(self) -> str:
        return self._settings.type.value

    def _get_chat_queue_key(self, chat_id: str | int) -> str:
        return (
            f"{self._get_channel_type()}:{self._channel_key}"
            f":message_queue:chat:{chat_id}"
        )

    def _get_chat_processing_lock_key(self, chat_id: str | int) -> str:
        return (
            f"{self._get_channel_type()}:{self._channel_key}"
            f":processing_lock:chat:{chat_id}"
        )

    @contextlib.asynccontextmanager
    async def _lock_chat_for_processing(self, chat_id: str | int):
        lock_key = self._get_chat_processing_lock_key(chat_id)
        while not await self._syncer.set_if_not_exists(
            lock_key, True, ttl=self.CHAT_LOCK_TTL_SECONDS
        ):
            await self._syncer.wait_delete(
                lock_key, timeout=self.CHAT_LOCK_WAIT_TIMEOUT
            )
        try:
            yield
        finally:
            await self._syncer.delete(lock_key)

