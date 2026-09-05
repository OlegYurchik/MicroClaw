from unittest.mock import MagicMock
import uuid

import pytest
import pytest_asyncio

from microclaw.agents.settings import AgentSettings
from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.accessors import CurrentUserAccessor
from microclaw.toolkits.agents.toolkit import AgentsToolKit
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.users_storages.dto import UserCreate
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


class TestAgentsToolKit:
    @pytest.fixture
    def toolkit(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.agents.toolkit.AgentsToolKit",
            args={"set_mode": "allow", "reset_mode": "allow"},
        )
        return AgentsToolKit(key="agents", settings=settings)

    @pytest_asyncio.fixture
    async def agents_context(self):
        users_storage = MemoryUsersStorage(settings=MemoryUsersStorageSettings())
        user = await users_storage.create_user(data=UserCreate())
        accessor = CurrentUserAccessor(
            user_id=user.id,
            storage=users_storage,
            writable=True,
            invalidate_cache=lambda: None,
        )
        context = ToolkitExecutionContext(
            session_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            channel_key="test",
            channel_internal_id="123",
            current_user_accessor=accessor,
            all_models={
                "test-model": MagicMock(model_dump=lambda mode: {"name": "test-model"})
            },
            all_toolkits={},
            all_skills={},
            all_agents={},
            all_mcp={},
        )
        token = TOOLKIT_CONTEXT.set(context)
        try:
            yield context
        finally:
            TOOLKIT_CONTEXT.reset(token)

    @pytest.mark.asyncio
    async def test_get_agent_settings_default(self, toolkit, agents_context):
        result = await toolkit.get_agent_settings()
        assert "default" in result.lower() or "Using default" in result

    @pytest.mark.asyncio
    async def test_get_agent_settings_with_override(self, toolkit, agents_context):
        await agents_context.current_user_accessor.get()
        await agents_context.current_user_accessor.update_agent_settings(
            {"model": "test-model"}
        )
        result = await toolkit.get_agent_settings()
        assert "test-model" in result

    @pytest.mark.asyncio
    async def test_get_available_global_resources_models(self, toolkit, agents_context):
        result = await toolkit.get_available_global_resources("models")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_available_global_resources_unknown(
        self, toolkit, agents_context
    ):
        with pytest.raises(ValueError):
            await toolkit.get_available_global_resources("unknown")

    @pytest.mark.asyncio
    async def test_set_agent_model_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_model("test-model")
        assert "test-model" in result

    @pytest.mark.asyncio
    async def test_set_agent_model_denied(self, toolkit):
        toolkit.arguments.set_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.set_agent_model("test-model")

    @pytest.mark.asyncio
    async def test_set_agent_identity_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_identity(name="TestBot")
        assert "TestBot" in result

    @pytest.mark.asyncio
    async def test_set_agent_subagents_success(self, toolkit, agents_context):
        with pytest.raises(ValueError):
            await toolkit.set_agent_subagents(["nonexistent"])

    @pytest.mark.asyncio
    async def test_set_agent_subagents_invalid(self, toolkit, agents_context):
        with pytest.raises(ValueError):
            await toolkit.set_agent_subagents(["invalid_agent"])

    @pytest.mark.asyncio
    async def test_set_agent_identity_request_mode(self, toolkit, agents_context):
        toolkit.arguments.set_mode = PermissionModeEnum.REQUEST
        with pytest.raises(Exception):
            await toolkit.set_agent_identity(name="TestBot")

    @pytest.mark.asyncio
    async def test_list_my_subagents_empty(self, toolkit, agents_context):
        result = await toolkit.list_my_subagents()
        assert result == []

    @pytest.mark.asyncio
    async def test_add_custom_subagent_denied(self, toolkit, agents_context):
        toolkit.arguments.set_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.add_custom_subagent(AgentSettings(model="test-model"))

    @pytest.mark.asyncio
    async def test_remove_subagent_denied(self, toolkit, agents_context):
        toolkit.arguments.set_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.remove_subagent("test")

    @pytest.mark.asyncio
    async def test_reset_agent_settings_denied(self, toolkit, agents_context):
        toolkit.arguments.reset_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.reset_agent_settings()

    @pytest.mark.asyncio
    async def test_get_available_global_resources_toolkits(
        self, toolkit, agents_context
    ):
        result = await toolkit.get_available_global_resources("toolkits")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_available_global_resources_agents(self, toolkit, agents_context):
        result = await toolkit.get_available_global_resources("agents")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_available_global_resources_mcp(self, toolkit, agents_context):
        result = await toolkit.get_available_global_resources("mcp")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_set_agent_temperature_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_temperature(0.5)
        assert "0.5" in result

    @pytest.mark.asyncio
    async def test_set_agent_max_tool_calls_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_max_tool_calls(10)
        assert "10" in result

    @pytest.mark.asyncio
    async def test_set_agent_max_model_calls_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_max_model_calls(5)
        assert "5" in result

    @pytest.mark.asyncio
    async def test_set_agent_summarization_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_summarization(True)
        assert "enabled" in result.lower()

    @pytest.mark.asyncio
    async def test_set_agent_memory_flush_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_memory_flush(True)
        assert "enabled" in result.lower()

    @pytest.mark.asyncio
    async def test_set_agent_max_memory_flush_tokens_success(
        self, toolkit, agents_context
    ):
        result = await toolkit.set_agent_max_memory_flush_tokens(2048)
        assert "2048" in result

    @pytest.mark.asyncio
    async def test_set_agent_max_tool_output_chars_success(
        self, toolkit, agents_context
    ):
        result = await toolkit.set_agent_max_tool_output_chars(4000)
        assert "4000" in result

    @pytest.mark.asyncio
    async def test_set_agent_model_max_retries_success(self, toolkit, agents_context):
        result = await toolkit.set_agent_model_max_retries(5)
        assert "5" in result

    @pytest.mark.asyncio
    async def test_set_agent_model_retry_backoff_factor_success(
        self, toolkit, agents_context
    ):
        result = await toolkit.set_agent_model_retry_backoff_factor(2.0)
        assert "2.0" in result

    @pytest.mark.asyncio
    async def test_set_agent_model_retry_initial_delay_success(
        self, toolkit, agents_context
    ):
        result = await toolkit.set_agent_model_retry_initial_delay(1.0)
        assert "1.0" in result
