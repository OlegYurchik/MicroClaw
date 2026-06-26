import asyncio
import datetime
import pathlib
import uuid
from typing import AsyncGenerator

import aiofiles

from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, Spending
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.sessions_storages.filters import SessionFilter, MessageFilter
from .dto import SessionData
from .settings import FilesystemSessionsStorageSettings


class FilesystemSessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: FilesystemSessionsStorageSettings):
        self._settings = settings
        self._locks: dict[uuid.UUID, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        self._settings.path.mkdir(parents=True, exist_ok=True)

    async def create_session(self, session_id: uuid.UUID | None = None) -> uuid.UUID:
        if session_id is None:
            session_id = uuid.uuid4()

        await self._write_session(session_id=session_id, data=SessionData())

    async def get_sessions(
            self,
            filter: SessionFilter | None = None,
            pagination: BasePagination | None = None,
            sort: BaseSort | None = None,
    ) -> AsyncGenerator[uuid.UUID]:
        if not self._settings.path.exists():
            return

        page_offset = pagination.offset if pagination else 0
        page_limit = pagination.limit if pagination else None
        
        session_ids = []
        
        for session_file in self._settings.path.glob("*.json"):
            if filter is not None and filter.created_at is not None:
                mtime = datetime.datetime.fromtimestamp(session_file.stat().st_mtime)
                if mtime.date() != filter.created_at.date():
                    continue

            try:
                session_id = uuid.UUID(session_file.stem)
                session_ids.append((session_id, session_file.stat().st_mtime))
            except ValueError:
                continue
        
        if sort is not None and sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc
            
            if sort_field in ["created_at", "updated_at", "mtime"]:
                session_ids.sort(key=lambda x: x[1], reverse=reverse)
        
        for i, (session_id, _) in enumerate(session_ids):
            if i < page_offset:
                continue
                
            if page_limit is not None and i >= page_offset + page_limit:
                break
                
            yield session_id

    async def add_message(self, session_id: uuid.UUID, message: AgentMessage):
        lock = await self._get_lock(session_id=session_id)
        async with lock:
            session_data = await self._read_session(session_id=session_id)
            session_data.messages.append(message)
            if message.spending:
                if message.is_summary:
                    session_data.context = message.spending.output_tokens
                else:
                    session_data.context = message.spending.get_total_tokens()

                if session_data.spending is None:
                    session_data.spending = message.spending
                else:
                    session_data.spending += message.spending
            await self._write_session(session_id=session_id, data=session_data)

    async def get_messages(
            self,
            filter: MessageFilter | None = None,
            pagination: BasePagination | None = None,
            sort: BaseSort | None = None,
            from_last_summarization: bool = True,
    ) -> AsyncGenerator[AgentMessage]:
        if filter is None or filter.session_id is None:
            return
            
        session_id = filter.session_id
        lock = await self._get_lock(session_id=session_id)
        async with lock:
            session_data = await self._read_session(session_id=session_id)

        messages = list(session_data.messages)
        
        if filter.is_summary is not None:
            messages = [m for m in messages if m.is_summary == filter.is_summary]
        if filter.role is not None:
            messages = [m for m in messages if m.role == filter.role]
        
        if sort is not None and sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc
            

            if sort_field == 'role':
                messages.sort(key=lambda m: m.role, reverse=reverse)
            elif sort_field == 'is_summary':
                messages.sort(key=lambda m: m.is_summary, reverse=reverse)
        
        if pagination and pagination.limit is not None:
            page_offset = pagination.offset if pagination else 0
            page_limit = pagination.limit if pagination else None
            end_index = min(page_offset + page_limit, len(messages)) if page_limit else len(messages)
            messages = messages[page_offset:end_index]
        
        if from_last_summarization:
            index = 0
            for i, message in enumerate(messages):
                if message.is_summary:
                    index = i
        else:
            index = 0

        for message in messages[index:]:
            yield message

    async def get_spending(self, session_id: uuid.UUID) -> Spending:
        lock = await self._get_lock(session_id=session_id)
        async with lock:
            session_data = await self._read_session(session_id=session_id)
        return session_data.spending or Spending()

    async def get_context_size(self, session_id: uuid.UUID) -> int:
        lock = await self._get_lock(session_id=session_id)
        async with lock:
            session_data = await self._read_session(session_id=session_id)
        return session_data.context

    async def _get_lock(self, session_id: uuid.UUID) -> asyncio.Lock:
        async with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            return self._locks[session_id]

    async def _read_session(self, session_id: uuid.UUID) -> SessionData:
        session_file = self._get_session_file_path(session_id)
        if not session_file.exists():
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
