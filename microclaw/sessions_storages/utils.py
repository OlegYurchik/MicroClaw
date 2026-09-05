from collections.abc import AsyncGenerator
import uuid

from microclaw.dto import AgentMessage
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface


async def get_messages_from_last_summarization(
    storage: SessionsStorageInterface,
    session_id: uuid.UUID,
) -> AsyncGenerator[AgentMessage]:
    messages = []
    async for message in storage.get_messages(filter_=MessageFilter(session_id={session_id})):
        messages.append(message)
    index = 0
    for i, message in enumerate(messages):
        if message.role == "summary":
            index = i
    for message in messages[index:]:
        yield message
