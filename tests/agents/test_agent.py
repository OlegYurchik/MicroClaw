from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.tools import StructuredTool

from microclaw.agents.agent import Agent
from microclaw.dto import AgentMessage
from microclaw.toolkits.base import BaseToolKit
from tests.factories import AssistantReply, AssistantToolCall, FakeChatModel


@pytest.mark.asyncio
async def test_ask_returns_accumulated_message_when_stream_false(make_agent, toolkit):
    client = FakeChatModel(
        steps=[AssistantReply(text="Hello "), AssistantReply(text="world")]
    )
    agent = make_agent(toolkits={"tools": toolkit}, client=client)

    messages = [AgentMessage(role="user", text="Hi")]
    result = [msg async for msg in agent.ask(messages, stream=False)]

    # result: accumulated message + spending message
    texts = [msg.text for msg in result if msg.text]
    assert texts == ["Hello world"]
    assert any(msg.spending is not None for msg in result)


@pytest.mark.asyncio
async def test_ask_returns_stream_chunks_when_stream_true(make_agent, toolkit):
    client = FakeChatModel(
        steps=[AssistantReply(text="chunk1"), AssistantReply(text="chunk2")]
    )
    agent = make_agent(toolkits={"tools": toolkit}, client=client)

    messages = [AgentMessage(role="user", text="Hi")]
    result = [msg async for msg in agent.ask(messages, stream=True)]

    texts = [msg.text for msg in result if msg.text]
    assert texts == ["chunk1", "chunk2"]
    assert sum(1 for msg in result if msg.spending is not None) == 1


@pytest.mark.asyncio
async def test_ask_yields_tool_messages(make_agent):
    @StructuredTool.from_function
    def calc(a: int) -> str:
        """Calc tool."""
        return str(a)

    toolkit = MagicMock(spec=BaseToolKit)
    toolkit.get_tools.return_value = [calc]

    client = FakeChatModel(
        steps=[
            AssistantToolCall(id="1", name="calc", args='{"a": 1}'),
            AssistantReply(text="Done"),
        ]
    )
    agent = make_agent(toolkits={"tools": toolkit}, client=client)

    messages = [AgentMessage(role="user", text="calculate")]
    result = [msg async for msg in agent.ask(messages, stream=False)]

    tool_msgs = [msg for msg in result if msg.role == "tool"]
    assert len(tool_msgs) == 2
    assert "Tool name: calc" in tool_msgs[0].text
    assert "Tool input" in tool_msgs[0].text
    assert "Tool name: calc" in tool_msgs[1].text
    assert "Tool output" in tool_msgs[1].text

    assistant_texts = [
        msg.text for msg in result if msg.role == "assistant" and msg.text
    ]
    assert "Done" in assistant_texts


@pytest.mark.asyncio
async def test_ask_yields_tool_error(make_agent):
    @StructuredTool.from_function
    def broken_tool() -> str:
        """Broken tool."""
        raise ValueError("boom")

    toolkit = MagicMock(spec=BaseToolKit)
    toolkit.get_tools.return_value = [broken_tool]

    client = FakeChatModel(
        steps=[
            AssistantToolCall(id="1", name="broken_tool", args="{}"),
            AssistantReply(text="Oops"),
        ]
    )
    agent = make_agent(toolkits={"tools": toolkit}, client=client)

    messages = [AgentMessage(role="user", text="break")]
    result = [msg async for msg in agent.ask(messages, stream=False)]

    tool_msgs = [msg for msg in result if msg.role == "tool"]
    assert len(tool_msgs) == 2
    assert "Tool name: broken_tool" in tool_msgs[0].text
    assert "Tool input" in tool_msgs[0].text
    assert "Tool name: broken_tool" in tool_msgs[1].text
    assert "Error" in tool_msgs[1].text


@pytest.mark.asyncio
async def test_ask_uses_channel_tools(make_agent, channel):
    tool_func = MagicMock(return_value="channel result")

    def _channel_tool_func(query: str) -> str:
        """Channel tool."""
        return tool_func(query)

    channel_tool = StructuredTool.from_function(_channel_tool_func, name="channel_tool")
    channel.get_toolkit.return_value.get_tools.return_value = [channel_tool]

    toolkit = MagicMock(spec=BaseToolKit)
    toolkit.get_tools.return_value = []

    client = FakeChatModel(
        steps=[
            AssistantToolCall(id="1", name="channel_tool", args='{"query": "hi"}'),
            AssistantReply(text="Done"),
        ]
    )
    agent = make_agent(toolkits={"tools": toolkit}, client=client)

    messages = [AgentMessage(role="user", text="use channel")]
    result = [msg async for msg in agent.ask(messages, channel=channel, stream=False)]

    tool_func.assert_called_once_with("hi")
    tool_msgs = [msg for msg in result if msg.role == "tool"]
    assert len(tool_msgs) == 2


# ---------------------------------------------------------------------------
# summarize_memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_memory(agent, client):
    client.ainvoke = AsyncMock(return_value=SimpleNamespace(content="memory summary"))
    result = await agent.summarize_memory("new context", "old context")
    assert isinstance(result, AgentMessage)
    assert result.role == "system"
    assert result.text == "memory summary"
    assert result.is_summary is True
    assert result.spending is not None


@pytest.mark.asyncio
async def test_summarize_memory_daily(agent, client):
    client.ainvoke = AsyncMock(return_value=SimpleNamespace(content="daily summary"))
    result = await agent.summarize_memory("new", "old", is_daily=True)
    assert result.text == "daily summary"
    assert result.is_summary is True
    assert result.spending is not None


# ---------------------------------------------------------------------------
# summarize_dialogue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_dialogue_empty_messages(agent):
    result = await agent.summarize_dialogue([])
    assert result.role == "system"
    assert result.text == "Dialog is empty"
    assert result.is_summary is True
    assert result.spending is None


@pytest.mark.asyncio
async def test_summarize_dialogue(agent, client):
    client.ainvoke = AsyncMock(return_value=SimpleNamespace(content="dialogue summary"))
    messages = [
        AgentMessage(role="user", text="hello"),
        AgentMessage(role="assistant", text="hi"),
    ]
    result = await agent.summarize_dialogue(messages)
    assert result.role == "system"
    assert "Summary of the previous dialogue:" in result.text
    assert "dialogue summary" in result.text
    assert result.is_summary is True
    assert result.spending is not None


# ---------------------------------------------------------------------------
# extract_important_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_important_info(agent, client):
    client.ainvoke = AsyncMock(
        return_value=SimpleNamespace(content="  important info  ")
    )
    result = await agent.extract_important_info(
        [AgentMessage(role="user", text="hello")]
    )
    assert result == "important info"


@pytest.mark.asyncio
async def test_extract_important_info_daily(agent, client):
    client.ainvoke = AsyncMock(return_value=SimpleNamespace(content="daily info"))
    result = await agent.extract_important_info([], is_daily=True)
    assert result == "daily info"


# ---------------------------------------------------------------------------
# get_model_context_window_size
# ---------------------------------------------------------------------------


def test_get_model_context_window_size_from_settings(agent):
    agent._model_settings.context_window_size = 4096
    assert agent.get_model_context_window_size() == 4096


def test_get_model_context_window_size_from_client_profile(agent):
    agent._model_settings.context_window_size = None

    class FakeClient:
        profile = {"max_input_tokens": 8192}

    agent._client = FakeClient()
    assert agent.get_model_context_window_size() == 8192


def test_get_model_context_window_size_from_client_modelname_to_contextsize(agent):
    agent._model_settings.context_window_size = None

    class FakeClient:
        model_name = "gpt-4"

        def modelname_to_contextsize(self, name):
            return 128_000

    agent._client = FakeClient()
    assert agent.get_model_context_window_size() == 128_000


def test_get_model_context_window_size_returns_none_when_unknown(agent):
    agent._model_settings.context_window_size = None

    class FakeClient:
        pass

    agent._client = FakeClient()
    assert agent.get_model_context_window_size() is None


# ---------------------------------------------------------------------------
# Other getters
# ---------------------------------------------------------------------------


def test_get_context_threshold_size(agent):
    assert (
        agent.get_context_threshold_size()
        == agent._model_settings.context_threshold_size
    )


def test_is_summarization_enabled(agent):
    assert agent.is_summarization_enabled() == agent._settings.enable_summarization


def test_is_memory_flush_enabled(agent):
    assert agent.is_memory_flush_enabled() == agent._settings.enable_memory_flush


def test_get_max_memory_flush_tokens(agent):
    assert (
        agent.get_max_memory_flush_tokens() == agent._settings.max_memory_flush_tokens
    )


# ---------------------------------------------------------------------------
# get_memory_toolkit
# ---------------------------------------------------------------------------


def test_get_memory_toolkit(agent, memory_toolkit):
    assert agent.get_memory_toolkit() is memory_toolkit


def test_get_memory_toolkit_none(
    agent_settings, model_settings, provider_settings, toolkit, syncer
):
    toolkits = {"tools": toolkit}
    instance = Agent(
        settings=agent_settings,
        model_settings=model_settings,
        provider_settings=provider_settings,
        toolkits=toolkits,
        syncer=syncer,
        mcp_settings={},
        client=MagicMock(),
    )
    assert instance.get_memory_toolkit() is None
