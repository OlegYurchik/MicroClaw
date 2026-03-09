import asyncio
import json
import pathlib
from typing import AsyncGenerator

import aiofiles

from microclaw.dto import AgentMessage, Spending
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from .dto import SessionData
from .settings import FilesystemSessionsStorageSettings


class FilesystemSessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: FilesystemSessionsStorageSettings):
        self._settings = settings
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        self._settings.path.mkdir(parents=True, exist_ok=True)

    async def add_message(self, session_id: str, message: AgentMessage):
        lock = await self._get_lock(session_id=session_id)
        async with lock:
            session_data = await self._read_session(session_id=session_id)
            session_data.messages.append(message)
            if message.spending is not None:
                if message.is_summary:
                    new_spending = message.spending.model_copy()
                    new_spending.cost += session_data.spending.cost
                    session_data.spending = new_spending
                else:
                    session_data.spending += message.spending
            await self._write_session(session_id=session_id, data=session_data)

    async def get_messages(
            self,
            session_id: str,
            last: int | None = None,
            from_last_summarization: bool = True,
    ) -> AsyncGenerator[AgentMessage]:
        session_data = await self._read_session(session_id=session_id)
        messages = session_data.messages
        if last is None:
            last = len(messages)
        messages = messages[-last:]
        if from_last_summarization:
            index = 0
            for i, message in enumerate(messages):
                if message.is_summary:
                    index = i
        else:
            index = 0

        for message in messages[index:]:
            yield message

    async def get_spending(self, session_id: str) -> Spending:
        session_data = await self._read_session(session_id=session_id)
        return session_data.spending

    async def _get_lock(self, session_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            return self._locks[session_id]

    async def _read_session(self, session_id: str) -> SessionData:
        session_file = self._get_session_file_path(session_id)
        if not session_file.exists():
            return SessionData()

        async with aiofiles.open(session_file, mode="r", encoding="utf-8") as f:
            content = await f.read()
        return SessionData.model_validate_json(content)

    async def _write_session(self, session_id: str, data: SessionData):
        session_file = self._get_session_file_path(session_id)
 
        async with aiofiles.open(session_file, mode="w", encoding="utf-8") as f:
            await f.write(data.model_dump_json(indent=2))

    def _get_session_file_path(self, session_id: str) -> pathlib.Path:
        return self._settings.path / f"{session_id}.json"
    

    

    
