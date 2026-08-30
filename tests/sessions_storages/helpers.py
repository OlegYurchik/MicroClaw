import uuid

from metaorm import AlreadyExistsError, NotFoundError
from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination
import pytest

from microclaw.dto import AgentMessage, AgentMessageRoleEnum, Spending
from microclaw.sessions_storages.dto import (
    MessageCreate,
    MessageUpdate,
    SessionCreate,
    SessionUpdate,
)
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface


async def assert_session_crud(storage: SessionsStorageInterface) -> None:
    s1 = await storage.create_session(
        data=SessionCreate(channel_key="tg", channel_internal_id="1")
    )
    s2 = await storage.create_session(
        data=SessionCreate(channel_key="vk", channel_internal_id="2")
    )

    fetched = await storage.get_session(s1.id)
    assert fetched is not None
    assert fetched.id == s1.id
    assert fetched.channel_key == "tg"
    assert fetched.context_size == 0

    assert await storage.get_session(uuid.uuid4()) is None

    sessions = [s async for s in storage.get_sessions()]
    assert len(sessions) == 2

    filtered = [
        s async for s in storage.get_sessions(filter_=SessionFilter(channel_key={"tg"}))
    ]
    assert len(filtered) == 1
    assert filtered[0].id == s1.id

    updated = await storage.update_session(s1.id, data=SessionUpdate(context_size=42))
    assert updated is not None
    assert updated.context_size == 42

    assert (
        await storage.update_session(uuid.uuid4(), data=SessionUpdate(context_size=1))
        is None
    )

    async for _ in storage.update_sessions(
        filter_=SessionFilter(channel_key={"vk"}),
        data=SessionUpdate(context_size=99),
    ):
        pass
    sessions = [
        s async for s in storage.get_sessions(filter_=SessionFilter(channel_key={"vk"}))
    ]
    assert len(sessions) == 1
    assert sessions[0].context_size == 99

    await storage.delete_session(s2.id)
    assert await storage.get_session(s2.id) is None

    await storage.delete_session(uuid.uuid4())

    with pytest.raises(AlreadyExistsError):
        await storage.create_session(
            data=SessionCreate(id=s1.id, channel_key="x", channel_internal_id="x")
        )


async def assert_message_crud(storage: SessionsStorageInterface) -> None:
    session = await storage.create_session(
        data=SessionCreate(channel_key="tg", channel_internal_id="1")
    )

    msg1 = await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(
                role=AgentMessageRoleEnum.USER,
                text="hello",
            ),
        )
    )
    assert msg1.text == "hello"

    await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(
                role=AgentMessageRoleEnum.ASSISTANT,
                text="world",
                spending=Spending(input_tokens=10, output_tokens=5),
            ),
        )
    )

    fetched_session = await storage.get_session(session.id)
    assert fetched_session is not None
    assert fetched_session.context_size == 15

    messages = [m async for m in storage.get_messages()]
    assert len(messages) == 2

    messages = [
        m
        async for m in storage.get_messages(
            filter_=MessageFilter(session_id={session.id})
        )
    ]
    assert len(messages) == 2

    messages = [
        m async for m in storage.get_messages(filter_=MessageFilter(role={"user"}))
    ]
    assert len(messages) == 1
    assert messages[0].text == "hello"

    updated = [
        m
        async for m in storage.update_messages(
            filter_=MessageFilter(role={"user"}),
            data=MessageUpdate(text="updated"),
        )
    ]
    assert len(updated) == 1
    assert updated[0].text == "updated"

    with pytest.raises(NotFoundError):
        await storage.create_message(
            data=MessageCreate(
                session_id=uuid.uuid4(),
                message=AgentMessage(role=AgentMessageRoleEnum.USER, text="orphan"),
            )
        )


async def assert_messages_from_last_summarization(
    storage: SessionsStorageInterface,
) -> None:
    session = await storage.create_session(
        data=SessionCreate(channel_key="tg", channel_internal_id="1")
    )

    await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(role=AgentMessageRoleEnum.USER, text="old"),
        )
    )
    await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(
                role=AgentMessageRoleEnum.SUMMARY,
                text="summary",
                spending=Spending(output_tokens=3),
            ),
        )
    )
    await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(role=AgentMessageRoleEnum.USER, text="new"),
        )
    )

    messages = [
        m async for m in storage.get_messages_from_last_summarization(session.id)
    ]
    assert len(messages) == 2
    texts = {m.text for m in messages}
    assert texts == {"summary", "new"}


async def assert_pagination_and_sort(storage: SessionsStorageInterface) -> None:
    await storage.create_session(
        data=SessionCreate(channel_key="a", channel_internal_id="1")
    )
    await storage.create_session(
        data=SessionCreate(channel_key="b", channel_internal_id="2")
    )
    await storage.create_session(
        data=SessionCreate(channel_key="c", channel_internal_id="3")
    )

    sessions = [
        s
        async for s in storage.get_sessions(
            pagination=OffsetPagination(limit=2, offset=0)
        )
    ]
    assert len(sessions) == 2

    sessions = [
        s
        async for s in storage.get_sessions(
            pagination=OffsetPagination(limit=2, offset=2)
        )
    ]
    assert len(sessions) == 1

    sessions = [
        s
        async for s in storage.get_sessions(
            sort=BaseSort(sort_by="channel_key", sort_by_order=SortByOrder.desc)
        )
    ]
    for i in range(len(sessions) - 1):
        assert sessions[i].channel_key >= sessions[i + 1].channel_key


async def assert_delete_sessions_filter(storage: SessionsStorageInterface) -> None:
    s1 = await storage.create_session(
        data=SessionCreate(channel_key="a", channel_internal_id="1")
    )
    await storage.create_session(
        data=SessionCreate(channel_key="b", channel_internal_id="2")
    )
    await storage.create_session(
        data=SessionCreate(channel_key="a", channel_internal_id="3")
    )

    await storage.delete_sessions(filter_=SessionFilter(channel_key={"a"}))
    sessions = [s async for s in storage.get_sessions()]
    assert len(sessions) == 1
    assert sessions[0].id == s1.id or sessions[0].channel_key == "b"


async def assert_delete_messages_filter(storage: SessionsStorageInterface) -> None:
    session = await storage.create_session(
        data=SessionCreate(channel_key="tg", channel_internal_id="1")
    )

    await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(role=AgentMessageRoleEnum.USER, text="a"),
        )
    )
    await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="b"),
        )
    )
    await storage.create_message(
        data=MessageCreate(
            session_id=session.id,
            message=AgentMessage(role=AgentMessageRoleEnum.TOOL, text="c"),
        )
    )

    await storage.delete_messages(filter_=MessageFilter(role={"user"}))
    messages = [m async for m in storage.get_messages()]
    assert len(messages) == 2
    roles = {m.role.value for m in messages}
    assert roles == {"assistant", "tool"}
