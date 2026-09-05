import asyncio
from collections.abc import AsyncGenerator
import datetime
import pathlib
import uuid

from .dto import SessionData
from .settings import FilesystemSessionsStorageSettings
import aiofiles
from metaorm import AlreadyExistsError, NotFoundError
from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, AgentMessageRoleEnum, Session
from microclaw.sessions_storages.dto import (
    MessageCreate,
    MessageUpdate,
    SessionCreate,
    SessionUpdate,
)
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface


class FilesystemSessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: FilesystemSessionsStorageSettings):
        self._settings = settings
        self._locks: dict[uuid.UUID, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        self._settings.path.mkdir(parents=True, exist_ok=True)

    async def create_session(
        self,
        data: SessionCreate,
    ) -> Session:
        session_id = data.id
        channel_key = data.channel_key
        channel_internal_id = data.channel_internal_id

        session_file = self._get_session_file_path(session_id)
        if await asyncio.to_thread(session_file.exists):
            raise AlreadyExistsError(f"Session {session_id} already exists")

        await self._write_session(
            session_id=session_id,
            data=SessionData(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            ),
        )
        return await self.get_session(filter_=SessionFilter(id={session_id}))

    async def get_session(
        self,
        filter_: SessionFilter,
        sort: BaseSort | None = None,
    ) -> Session | None:
        session_id = next(iter(filter_.id), None)
        if session_id is None:
            return None
        session_file = self._get_session_file_path(session_id)
        if not await asyncio.to_thread(session_file.exists):
            return None

        stat = await asyncio.to_thread(session_file.stat)
        session_data = await self._read_session(session_id=session_id)
        return Session(
            id=session_id,
            channel_key=session_data.channel_key,
            channel_internal_id=session_data.channel_internal_id,
            context_size=session_data.context,
            spending=session_data.spending,
            created_at=datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc),
            updated_at=datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc),
        )

    async def get_sessions(
        self,
        filter_: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Session]:
        if not await asyncio.to_thread(self._settings.path.exists):
            return

        page_offset = pagination.offset if pagination else 0
        page_limit = pagination.limit if pagination else None

        sessions = []

        session_files = await asyncio.to_thread(lambda: list(self._settings.path.glob("*.json")))
        for session_file in session_files:
            stat = await asyncio.to_thread(session_file.stat)
            if filter_ is not None:
                ctime = datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc)
                if filter_.created_at and ctime.date() not in {d.date() for d in filter_.created_at}:
                    continue
                if filter_.created_at__gt is not None and ctime <= filter_.created_at__gt:
                    continue
                if filter_.created_at__lt is not None and ctime >= filter_.created_at__lt:
                    continue
                if filter_.updated_at__gt is not None and mtime <= filter_.updated_at__gt:
                    continue
                if filter_.updated_at__lt is not None and mtime >= filter_.updated_at__lt:
                    continue

            try:
                session_id = uuid.UUID(session_file.stem)
                session_data = await self._read_session(session_id)
                if filter_ is not None and filter_.channel_key:
                    if session_data.channel_key not in filter_.channel_key:
                        continue
                sessions.append(
                    Session(
                        id=session_id,
                        channel_key=session_data.channel_key,
                        channel_internal_id=session_data.channel_internal_id,
                        context_size=session_data.context,
                        spending=session_data.spending,
                        created_at=datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc),
                        updated_at=datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc),
                    )
                )
            except ValueError:
                continue

        if sort is not None and sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc

            if sort_field in ["created_at", "updated_at"]:
                sessions.sort(key=lambda s: s.created_at if sort_field == "created_at" else s.updated_at, reverse=reverse)
            elif sort_field == "id":
                sessions.sort(key=lambda s: s.id, reverse=reverse)
            elif sort_field == "channel_key":
                sessions.sort(key=lambda s: s.channel_key, reverse=reverse)

        for i, session in enumerate(sessions):
            if i < page_offset:
                continue

            if page_limit is not None and i >= page_offset + page_limit:
                break

            yield session

    async def update_sessions(
        self,
        filter_: SessionFilter | None = None,
        *, data: SessionUpdate,
    ) -> AsyncGenerator[Session]:
        session_files = await asyncio.to_thread(lambda: list(self._settings.path.glob("*.json")))
        for session_file in session_files:
            try:
                session_id = uuid.UUID(session_file.stem)
            except ValueError:
                continue
            lock = await self._get_lock(session_id=session_id)
            async with lock:
                if not await asyncio.to_thread(session_file.exists):
                    continue
                session_data = await self._read_session(session_id)
                if filter_ is not None:
                    if filter_.id and session_id not in filter_.id:
                        continue
                    if filter_.channel_key and session_data.channel_key not in filter_.channel_key:
                        continue
                    stat = await asyncio.to_thread(session_file.stat)
                    ctime = datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc)
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc)
                    if filter_.created_at and ctime.date() not in {d.date() for d in filter_.created_at}:
                        continue
                    if filter_.created_at__gt is not None and ctime <= filter_.created_at__gt:
                        continue
                    if filter_.created_at__lt is not None and ctime >= filter_.created_at__lt:
                        continue
                    if filter_.updated_at__gt is not None and mtime <= filter_.updated_at__gt:
                        continue
                    if filter_.updated_at__lt is not None and mtime >= filter_.updated_at__lt:
                        continue
                if data.context_size is not None:
                    session_data.context = data.context_size
                if data.spending is not None:
                    session_data.spending = data.spending
                await self._write_session(session_id=session_id, data=session_data)
                stat = await asyncio.to_thread(session_file.stat)
                yield Session(
                    id=session_id,
                    channel_key=session_data.channel_key,
                    channel_internal_id=session_data.channel_internal_id,
                    context_size=session_data.context,
                    spending=session_data.spending,
                    created_at=datetime.datetime.fromtimestamp(stat.st_ctime, tz=datetime.timezone.utc),
                    updated_at=datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc),
                )

    async def delete_session(self, filter_: SessionFilter) -> None:
        session_id = next(iter(filter_.id), None)
        if session_id is None:
            return
        session_file = self._get_session_file_path(session_id)
        if not await asyncio.to_thread(session_file.exists):
            return

        try:
            await asyncio.to_thread(session_file.unlink)
        except FileNotFoundError:
            pass
        self._locks.pop(session_id, None)

    async def delete_sessions(self, filter_: SessionFilter | None = None) -> None:
        session_files = await asyncio.to_thread(lambda: list(self._settings.path.glob("*.json")))
        for session_file in session_files:
            try:
                session_id = uuid.UUID(session_file.stem)
            except ValueError:
                continue
            lock = await self._get_lock(session_id=session_id)
            async with lock:
                session_data = await self._read_session(session_id)
                if filter_ is not None:
                    if filter_.id and session_id not in filter_.id:
                        continue
                    if filter_.channel_key and session_data.channel_key not in filter_.channel_key:
                        continue
                    stat = await asyncio.to_thread(session_file.stat)
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc)
                    if filter_.created_at and mtime.date() not in {d.date() for d in filter_.created_at}:
                        continue
                    if filter_.created_at__gt is not None and mtime <= filter_.created_at__gt:
                        continue
                    if filter_.created_at__lt is not None and mtime >= filter_.created_at__lt:
                        continue
                    if filter_.updated_at__gt is not None and mtime <= filter_.updated_at__gt:
                        continue
                    if filter_.updated_at__lt is not None and mtime >= filter_.updated_at__lt:
                        continue
                try:
                    await asyncio.to_thread(session_file.unlink)
                except FileNotFoundError:
                    pass
                self._locks.pop(session_id, None)

    async def create_message(self, data: MessageCreate) -> AgentMessage:
        session_file = self._get_session_file_path(data.session_id)
        lock = await self._get_lock(session_id=data.session_id)
        async with lock:
            if not await asyncio.to_thread(session_file.exists):
                raise NotFoundError(f"Session {data.session_id} not found")
            session_data = await self._read_session(session_id=data.session_id)
            message = data.message
            if message.id is None:
                message = message.model_copy(update={"id": uuid.uuid4()})
            session_data.messages.append(message)
            if message.spending:
                if message.role == AgentMessageRoleEnum.SUMMARY:
                    session_data.context = message.spending.output_tokens
                elif message.context_tokens is not None:
                    session_data.context = message.context_tokens
                else:
                    session_data.context = (
                        message.spending.input_tokens + message.spending.output_tokens
                    )

                if session_data.spending is None:
                    session_data.spending = message.spending
                else:
                    session_data.spending += message.spending
            await self._write_session(session_id=data.session_id, data=session_data)
        return message

    async def get_message(
        self,
        filter_: MessageFilter,
        sort: BaseSort | None = None,
    ) -> AgentMessage | None:
        async for message in self.get_messages(filter_=filter_, pagination=BasePagination(limit=1, offset=0), sort=sort):
            return message
        return None

    async def get_messages(
        self,
        filter_: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[AgentMessage]:
        if filter_ is not None and filter_.session_id:
            session_ids = list(filter_.session_id)
        else:
            session_ids = []
            session_files = await asyncio.to_thread(lambda: list(self._settings.path.glob("*.json")))
            for session_file in session_files:
                try:
                    session_ids.append(uuid.UUID(session_file.stem))
                except ValueError:
                    continue

        # Stream directly when no sort is needed
        if sort is None:
            page_offset = pagination.offset if pagination else 0
            page_limit = pagination.limit if pagination else None
            count = 0
            for session_id in session_ids:
                lock = await self._get_lock(session_id=session_id)
                async with lock:
                    session_data = await self._read_session(session_id=session_id)
                for message in session_data.messages:
                    if filter_ is not None and filter_.id and message.id not in filter_.id:
                        continue
                    if filter_ is not None and filter_.role and message.role not in filter_.role:
                        continue
                    if count < page_offset:
                        count += 1
                        continue
                    if page_limit is not None and count >= page_offset + page_limit:
                        return
                    count += 1
                    yield message
            return

        # When sorting is required, collect only messages (avoid tuples)
        all_messages: list[AgentMessage] = []
        for session_id in session_ids:
            lock = await self._get_lock(session_id=session_id)
            async with lock:
                session_data = await self._read_session(session_id=session_id)
            for message in session_data.messages:
                if filter_ is not None and filter_.id and message.id not in filter_.id:
                    continue
                if filter_ is not None and filter_.role and message.role not in filter_.role:
                    continue
                all_messages.append(message)

        if sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc

            if sort_field == "role":
                all_messages.sort(key=lambda m: m.role, reverse=reverse)

        if pagination and pagination.limit is not None:
            page_offset = pagination.offset if pagination else 0
            page_limit = pagination.limit if pagination else None
            end_index = (
                min(page_offset + page_limit, len(all_messages))
                if page_limit
                else len(all_messages)
            )
            all_messages = all_messages[page_offset:end_index]

        for message in all_messages:
            yield message

    async def update_messages(
        self,
        filter_: MessageFilter | None = None,
        *, data: MessageUpdate,
    ) -> AsyncGenerator[AgentMessage]:
        if filter_ is not None and filter_.session_id:
            session_ids = list(filter_.session_id)
        else:
            session_ids = []
            session_files = await asyncio.to_thread(lambda: list(self._settings.path.glob("*.json")))
            for session_file in session_files:
                try:
                    session_ids.append(uuid.UUID(session_file.stem))
                except ValueError:
                    continue

        for session_id in session_ids:
            lock = await self._get_lock(session_id=session_id)
            async with lock:
                session_data = await self._read_session(session_id=session_id)
                updated = False
                new_messages: list[AgentMessage] = []
                yielded_messages: list[AgentMessage] = []
                for message in session_data.messages:
                    if filter_ is not None and filter_.id and message.id not in filter_.id:
                        new_messages.append(message)
                        continue
                    if filter_ is not None and filter_.role and message.role not in filter_.role:
                        new_messages.append(message)
                        continue
                    update = {}
                    if data.role is not None:
                        update["role"] = data.role
                    if data.text is not None:
                        update["text"] = data.text
                    if update:
                        message = message.model_copy(update=update)
                        updated = True
                    new_messages.append(message)
                    yielded_messages.append(message)
                if updated:
                    session_data.messages = new_messages
                    await self._write_session(session_id=session_id, data=session_data)
            for message in yielded_messages:
                yield message

    async def delete_message(self, filter_: MessageFilter) -> None:
        if filter_.id:
            await self.delete_messages(filter_=filter_)
        else:
            await self.delete_messages(filter_=filter_)

    async def delete_messages(self, filter_: MessageFilter | None = None) -> None:
        if filter_ is not None and filter_.session_id:
            session_ids = list(filter_.session_id)
        else:
            session_ids = []
            session_files = await asyncio.to_thread(lambda: list(self._settings.path.glob("*.json")))
            for session_file in session_files:
                try:
                    session_ids.append(uuid.UUID(session_file.stem))
                except ValueError:
                    continue

        for session_id in session_ids:
            lock = await self._get_lock(session_id=session_id)
            async with lock:
                session_data = await self._read_session(session_id=session_id)
                if filter_ is not None and filter_.id:
                    session_data.messages = [
                        m for m in session_data.messages if m.id not in filter_.id
                    ]
                elif filter_ is not None and filter_.role:
                    session_data.messages = [
                        m for m in session_data.messages if m.role not in filter_.role
                    ]
                else:
                    session_data.messages = []
                await self._write_session(session_id=session_id, data=session_data)

    async def _get_lock(self, session_id: uuid.UUID) -> asyncio.Lock:
        async with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            return self._locks[session_id]

    async def _read_session(self, session_id: uuid.UUID) -> SessionData:
        session_file = self._get_session_file_path(session_id)
        if not await asyncio.to_thread(session_file.exists):
            return SessionData()

        async with aiofiles.open(session_file, mode="r", encoding="utf-8") as f:
            content = await f.read()
        return SessionData.model_validate_json(content)

    async def _write_session(self, session_id: uuid.UUID, data: SessionData):
        session_file = self._get_session_file_path(session_id)
        async with aiofiles.open(session_file, mode="w", encoding="utf-8") as f:
            await f.write(data.model_dump_json(indent=2))

    def _get_session_file_path(self, session_id: uuid.UUID) -> pathlib.Path:
        return self._settings.path / f"{session_id}.json"
