from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.webhooks.agent_webhook import (
    AgentWebhook,
    AgentWebhookPayload,
    AgentWebhookSettings,
)
from microclaw.webhooks.base import WebhookResponse


class TestAgentWebhook:
    @pytest.mark.asyncio
    async def test_handle_without_channel(self, make_agent, resolver):
        from tests.factories import AssistantReply, FakeChatModel

        client = FakeChatModel(steps=[AssistantReply(text="ok")])
        agent = make_agent(toolkits={}, client=client)
        resolver.resolve_agents.return_value = {"default": agent}

        webhook = AgentWebhook(
            arguments=AgentWebhookSettings(agent="default"),
            resolver=resolver,
        )
        result = await webhook.handle(AgentWebhookPayload(text="Hello world"))

        assert isinstance(result, WebhookResponse)
        assert result.body == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_handle_with_channel(self, make_agent, resolver, sessions_storage, users_storage):
        from tests.factories import AssistantReply, FakeChatModel

        client = FakeChatModel(steps=[AssistantReply(text="ok")])
        agent = make_agent(toolkits={}, client=client)
        resolver.resolve_agents.return_value = {"default": agent}

        channel_mock = MagicMock()
        channel_mock.get_sessions_storage.return_value = sessions_storage
        channel_mock.get_users_storage.return_value = users_storage
        channel_mock.start_conversation = AsyncMock()
        resolver.resolve_channels.return_value = {"telegram": channel_mock}

        webhook = AgentWebhook(
            arguments=AgentWebhookSettings(
                agent="default",
                channel="telegram",
                channel_internal_id="123456",
            ),
            resolver=resolver,
        )
        result = await webhook.handle(AgentWebhookPayload(text="Hello world"))

        assert isinstance(result, WebhookResponse)
        assert result.body == {"status": "ok"}
        channel_mock.start_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_payload_without_text_serializes_to_json(self, resolver):
        from tests.conftest import _async_gen

        agent_mock = MagicMock()
        agent_mock.ask.return_value = _async_gen([])
        resolver.resolve_agents.return_value = {"default": agent_mock}

        webhook = AgentWebhook(
            arguments=AgentWebhookSettings(agent="default"),
            resolver=resolver,
        )
        result = await webhook.handle(AgentWebhookPayload(action="delete", id="42"))

        assert isinstance(result, WebhookResponse)
        messages = agent_mock.ask.call_args.kwargs["messages"]
        assert len(messages) == 1
        assert '"action": "delete"' in messages[0].text
        assert '"id": "42"' in messages[0].text

    @pytest.mark.asyncio
    async def test_handle_agent_not_found_raises(self, resolver):
        resolver.resolve_agents.return_value = {}

        webhook = AgentWebhook(
            arguments=AgentWebhookSettings(agent="missing"),
            resolver=resolver,
        )
        with pytest.raises(RuntimeError, match="Agent not found for webhook"):
            await webhook.handle(AgentWebhookPayload(text="Hello"))

    @pytest.mark.asyncio
    async def test_handle_channel_not_found_raises(self, make_agent, resolver):
        from tests.factories import AssistantReply, FakeChatModel

        client = FakeChatModel(steps=[AssistantReply(text="ok")])
        agent = make_agent(toolkits={}, client=client)
        resolver.resolve_agents.return_value = {"default": agent}
        resolver.resolve_channels.return_value = {}

        webhook = AgentWebhook(
            arguments=AgentWebhookSettings(
                agent="default",
                channel="missing",
                channel_internal_id="123",
            ),
            resolver=resolver,
        )
        with pytest.raises(RuntimeError, match="Channel not found for webhook"):
            await webhook.handle(AgentWebhookPayload(text="Hello"))
