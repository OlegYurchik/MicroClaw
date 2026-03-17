import uuid
from typing import Self

from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface


class AgentMessageHandler:
    def __init__(self):
        self._last_chunked_message_id: str | None = None
        self._is_new_message_chunk: bool = True

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._last_chunked_message_id = None
        self._is_new_message_chunk = False

    @property
    def is_new_message_chunk(self) -> bool:
        return self._is_new_message_chunk

    async def register_new_message(self, new_message: AgentMessage):
        self._is_new_message_chunk = (
            new_message.chunked_message_id is None or
            new_message.chunked_message_id != self._last_chunked_message_id
        )
        self._last_chunked_message_id = new_message.chunked_message_id

        await self.handle_new_message(new_message=new_message)

    async def handle_new_message(self, new_message: AgentMessage):
        pass


class AgentMessageSaver(AgentMessageHandler):
    def __init__(
            self,
            sessions_storage: SessionsStorageInterface,
            session_id: uuid.UUID,
    ):
        super().__init__()

        self._messages: list[AgentMessage] = []
        self._sessions_storage = sessions_storage
        self._session_id = session_id

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._flush_messages()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def handle_new_message(self, new_message: AgentMessage):
        if self.is_new_message_chunk:
            await self._flush_messages()
            self._messages.append(new_message.model_copy())
        elif new_message.text:
            self._messages[-1].text += new_message.text

    async def _flush_messages(self):
        for message in self._messages:
            await self._sessions_storage.add_message(
                session_id=self._session_id,
                message=message,
            )
        self._messages = []
