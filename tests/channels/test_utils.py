import pytest

from microclaw.channels.utils import AgentMessageCollector, AgentMessageSaver
from microclaw.dto import AgentMessage, AgentMessageRoleEnum
from microclaw.sessions_storages.dto import SessionCreate
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage


@pytest.fixture
def sessions_storage():
    return MemorySessionsStorage(settings=MemorySessionsStorageSettings())


@pytest.mark.asyncio
async def test_collector_aenter_aexit():
    collector = AgentMessageCollector()
    async with collector:
        pass
    assert collector._last_chunked_message_id is None
    assert collector.is_new_message_chunk is False


@pytest.mark.asyncio
async def test_collector_register_new_message_first():
    collector = AgentMessageCollector()
    msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
    await collector.register_new_message(msg)
    assert collector.is_new_message_chunk is True
    assert collector._last_chunked_message_id is None


@pytest.mark.asyncio
async def test_collector_register_new_message_same_chunk():
    collector = AgentMessageCollector()
    msg1 = AgentMessage(
        role=AgentMessageRoleEnum.ASSISTANT, text="hello", chunked_message_id="c1"
    )
    msg2 = AgentMessage(
        role=AgentMessageRoleEnum.ASSISTANT, text=" world", chunked_message_id="c1"
    )
    await collector.register_new_message(msg1)
    await collector.register_new_message(msg2)
    assert collector.is_new_message_chunk is False


@pytest.mark.asyncio
async def test_collector_register_new_message_different_chunk():
    collector = AgentMessageCollector()
    msg1 = AgentMessage(
        role=AgentMessageRoleEnum.ASSISTANT, text="hello", chunked_message_id="c1"
    )
    msg2 = AgentMessage(
        role=AgentMessageRoleEnum.ASSISTANT, text="world", chunked_message_id="c2"
    )
    await collector.register_new_message(msg1)
    await collector.register_new_message(msg2)
    assert collector.is_new_message_chunk is True


@pytest.mark.asyncio
async def test_saver_flushes_on_new_chunk(sessions_storage):
    session = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="test", channel_internal_id="")
    )).id
    saver = AgentMessageSaver(sessions_storage=sessions_storage, session_id=session)

    async with saver:
        msg1 = AgentMessage(
            role=AgentMessageRoleEnum.ASSISTANT, text="hello", chunked_message_id="c1"
        )
        await saver.register_new_message(msg1)

    # After exit, message should be flushed
    messages = []
    async for m in sessions_storage.get_messages(
        filter_=MessageFilter(session_id={session})
    ):
        messages.append(m)

    assert len(messages) == 1
    assert messages[0].text == "hello"


@pytest.mark.asyncio
async def test_saver_appends_to_same_chunk(sessions_storage):
    session = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="test", channel_internal_id="")
    )).id
    saver = AgentMessageSaver(sessions_storage=sessions_storage, session_id=session)

    async with saver:
        msg1 = AgentMessage(
            role=AgentMessageRoleEnum.ASSISTANT, text="hello", chunked_message_id="c1"
        )
        msg2 = AgentMessage(
            role=AgentMessageRoleEnum.ASSISTANT, text=" world", chunked_message_id="c1"
        )
        await saver.register_new_message(msg1)
        await saver.register_new_message(msg2)

    messages = []
    async for m in sessions_storage.get_messages(
        filter_=MessageFilter(session_id={session})
    ):
        messages.append(m)

    assert len(messages) == 1
    assert messages[0].text == "hello world"


@pytest.mark.asyncio
async def test_saver_aexit_with_cancelled_error(sessions_storage):
    session = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="test", channel_internal_id="")
    )).id
    saver = AgentMessageSaver(sessions_storage=sessions_storage, session_id=session)

    # Simulate CancelledError during flush by making create_message raise it
    original = sessions_storage.create_message
    sessions_storage.create_message = lambda **kwargs: (_ for _ in ()).throw(
        KeyboardInterrupt
    )

    try:
        async with saver:
            msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
            await saver.register_new_message(msg)
    except KeyboardInterrupt:
        pass
    finally:
        sessions_storage.create_message = original
