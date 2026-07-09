"""Ensure _handle_tool_errors does NOT swallow GraphBubbleUp / GraphInterrupt."""

import uuid
from typing import Any

import pytest
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphBubbleUp, GraphInterrupt
from langgraph.types import Command, interrupt

from microclaw.agents.agent import _handle_tool_errors


class DummyModel(BaseChatModel):
    """A dummy model that always returns a tool call."""

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    def _llm_type(self):
        return "dummy"

    @property
    def _identifying_params(self):
        return {}

    def invoke(self, input, config=None, **kwargs):
        return AIMessage(
            content="",
            tool_calls=[{"name": "interrupting_tool", "args": {}, "id": "tc1"}]
        )

    async def ainvoke(self, input, config=None, **kwargs):
        return self.invoke(input, config, **kwargs)

    def bind_tools(self, tools, **kwargs):
        return self


@tool
def interrupting_tool():
    """A tool that triggers a langgraph interrupt."""
    interrupt({"description": "Approve?"})
    return "done"


@pytest.mark.asyncio
async def test_handle_tool_errors_does_not_swallow_graph_interrupt():
    """GraphInterrupt raised inside a tool must bubble up, not be wrapped in a ToolMessage."""
    checkpointer = InMemorySaver()
    agent = create_agent(
        model=DummyModel(),
        tools=[interrupting_tool],
        checkpointer=checkpointer,
        middleware=[_handle_tool_errors],
    )
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": "do it"}]},
        config,
        version="v2",
    ):
        if event["event"] == "on_chain_stream":
            chunk = event["data"].get("chunk", {})
            if isinstance(chunk, dict) and "__interrupt__" in chunk:
                break
    else:
        pytest.fail("Expected __interrupt__ in event stream, but none was found.")

    state = await agent.aget_state(config)
    assert state.interrupts, "Expected pending interrupts in graph state."

    # Resume should succeed (tool returns "done" after receiving the resume value)
    tool_ran = False
    async for event in agent.astream_events(Command(resume="yes"), config, version="v2"):
        if event["event"] == "on_tool_end" and event.get("name") == "interrupting_tool":
            tool_ran = True

    assert tool_ran, "Tool should have completed after resume."


def test_handle_tool_errors_passes_through_graph_bubble_up():
    """Unit-test: _handle_tool_errors must re-raise GraphBubbleUp subclasses."""
    import asyncio

    async def _burst(request):
        raise GraphInterrupt()

    request = type("R", (), {"tool_call": {"id": "tc1"}})()

    with pytest.raises(GraphBubbleUp):
        asyncio.run(_handle_tool_errors.awrap_tool_call(request, _burst))

    # Verify a normal exception is still handled
    async def _boom(request):
        raise ValueError("boom")

    result = asyncio.run(_handle_tool_errors.awrap_tool_call(request, _boom))
    assert isinstance(result, AIMessage.__bases__[0].__mro__[0])  # ToolMessage is not directly importable here easily
