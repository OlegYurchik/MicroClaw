from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.agents.settings import AgentSettings
from microclaw.cron.settings import CronTaskSettings
from microclaw.cron.tasks.agent import AgentCronTask
from microclaw.dto import UserChannel


class TestAgentCronTask:
    @pytest.fixture
    def resolver(self):
        mock = MagicMock()
        mock.resolve_channels = AsyncMock(return_value={})
        mock.resolve_agents = AsyncMock(return_value={})
        mock.resolve_agent = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def base_settings(self):
        return CronTaskSettings(
            path="microclaw.cron.tasks.agent.AgentCronTask",
            cron="0 0 * * *",
            args={"task": "test task"},
        )

    @pytest.mark.asyncio
    async def test_do_before_channel_not_found(self, resolver, base_settings):
        settings = base_settings.model_copy(
            update={
                "args": {
                    "task": "test",
                    "channel": "missing",
                    "channel_internal_id": "1",
                    "agent": "missing",
                }
            }
        )
        task = AgentCronTask(key="test", settings=settings, resolver=resolver)
        with pytest.raises(RuntimeError, match="Channel not found"):
            await task.do_before()

    @pytest.mark.asyncio
    async def test_do_before_agent_not_found(self, resolver, base_settings):
        settings = base_settings.model_copy(
            update={"args": {"task": "test", "agent": "missing"}}
        )
        task = AgentCronTask(key="test", settings=settings, resolver=resolver)
        with pytest.raises(RuntimeError, match="Agent not found"):
            await task.do_before()

    @pytest.mark.asyncio
    async def test_do_before_agent_by_settings(self, resolver, base_settings):
        settings = base_settings.model_copy(
            update={
                "args": {
                    "task": "test",
                    "agent": AgentSettings(model="test-model"),
                }
            }
        )
        mock_agent = MagicMock()
        resolver.resolve_agent = AsyncMock(return_value=mock_agent)
        task = AgentCronTask(key="test", settings=settings, resolver=resolver)
        await task.do_before()
        assert task._agent is mock_agent

    @pytest.mark.asyncio
    async def test_execute_without_channel(self, resolver, base_settings):
        settings = base_settings.model_copy(
            update={"args": {"task": "test", "agent": "test_agent"}}
        )

        async def mock_ask(*args, **kwargs):
            return
            yield

        mock_agent = MagicMock()
        mock_agent.ask = mock_ask
        resolver.resolve_agents = AsyncMock(return_value={"test_agent": mock_agent})

        task = AgentCronTask(key="test", settings=settings, resolver=resolver)
        await task.do_before()
        await task.execute()

    @pytest.mark.asyncio
    async def test_execute_with_channel_existing_user(self, resolver, base_settings):
        channel_internal_id = "123"
        settings = base_settings.model_copy(
            update={
                "args": {
                    "task": "test",
                    "channel": "test_channel",
                    "channel_internal_id": channel_internal_id,
                    "agent": "test_agent",
                    "create_new_session": False,
                }
            }
        )

        async def mock_ask(*args, **kwargs):
            return
            yield

        mock_agent = MagicMock()
        mock_agent.ask = mock_ask
        resolver.resolve_agents = AsyncMock(return_value={"test_agent": mock_agent})

        mock_channel = MagicMock()
        mock_channel.start_conversation = AsyncMock()
        mock_sessions_storage = MagicMock()
        mock_users_storage = MagicMock()
        mock_channel.get_sessions_storage.return_value = mock_sessions_storage
        mock_channel.get_users_storage.return_value = mock_users_storage

        user_channel = UserChannel(
            user_id=uuid.uuid4(),
            channel_key="test_channel",
            channel_internal_id=channel_internal_id,
            actual_session_id=uuid.uuid4(),
        )

        async def mock_get_user_channels(*args, **kwargs):
            yield user_channel

        mock_users_storage.get_user_channels = mock_get_user_channels
        mock_users_storage.get_user = AsyncMock(
            return_value=MagicMock(id=user_channel.user_id)
        )

        resolver.resolve_channels = AsyncMock(
            return_value={"test_channel": mock_channel}
        )

        task = AgentCronTask(key="test", settings=settings, resolver=resolver)
        await task.do_before()
        await task.execute()

        mock_channel.start_conversation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_with_channel_new_user(self, resolver, base_settings):
        channel_internal_id = "456"
        settings = base_settings.model_copy(
            update={
                "args": {
                    "task": "test",
                    "channel": "test_channel",
                    "channel_internal_id": channel_internal_id,
                    "agent": "test_agent",
                    "create_new_session": True,
                }
            }
        )

        async def mock_ask(*args, **kwargs):
            return
            yield

        mock_agent = MagicMock()
        mock_agent.ask = mock_ask
        resolver.resolve_agents = AsyncMock(return_value={"test_agent": mock_agent})

        mock_channel = MagicMock()
        mock_channel.start_conversation = AsyncMock()
        mock_sessions_storage = MagicMock()
        mock_users_storage = MagicMock()
        mock_channel.get_sessions_storage.return_value = mock_sessions_storage
        mock_channel.get_users_storage.return_value = mock_users_storage

        async def mock_get_user_channels(*args, **kwargs):
            return
            yield

        mock_users_storage.get_user_channels = mock_get_user_channels
        new_user = MagicMock(id=uuid.uuid4())
        mock_users_storage.create_user = AsyncMock(return_value=new_user)
        mock_sessions_storage.create_session = AsyncMock()
        mock_channel.ensure_user_channel_attached = AsyncMock()

        resolver.resolve_channels = AsyncMock(
            return_value={"test_channel": mock_channel}
        )

        task = AgentCronTask(key="test", settings=settings, resolver=resolver)
        await task.do_before()
        await task.execute()

        mock_sessions_storage.create_session.assert_awaited_once()
        mock_channel.ensure_user_channel_attached.assert_awaited_once()
        mock_channel.start_conversation.assert_awaited_once()


async def async_generator(items):
    for item in items:
        yield item
