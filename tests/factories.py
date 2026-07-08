from typing import Any, AsyncIterator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import BaseModel, Field, PrivateAttr
import uuid

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.dto import AgentMessage, DecisionEnum
from microclaw.sessions_storages.filters import MessageFilter


class AssistantReply(BaseModel):
    text: str


class AssistantToolCall(BaseModel):
    id: str
    name: str
    args: str


class FakeChatModel(BaseChatModel):
    steps: list[AssistantReply | AssistantToolCall] = Field(default_factory=list)
    _index: int = PrivateAttr(default=0)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop=None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        text_steps = self._consume_text_steps()
        if text_steps:
            return ChatResult(
                generations=[
                    ChatGeneration(message=AIMessageChunk(content="".join(text_steps)))
                ]
            )
        if self._index < len(self.steps):
            return ChatResult(
                generations=[ChatGeneration(message=self._next_tool_call())]
            )
        return ChatResult(
            generations=[ChatGeneration(message=AIMessageChunk(content=""))]
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop=None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop=None,
        run_manager=None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if self._index < len(self.steps) and isinstance(
            self.steps[self._index], AssistantReply
        ):
            for text in self._consume_text_steps():
                yield ChatGenerationChunk(message=AIMessageChunk(content=text))
        elif self._index < len(self.steps):
            yield ChatGenerationChunk(message=self._next_tool_call())
        else:
            yield ChatGenerationChunk(message=AIMessageChunk(content=""))

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self) -> str:
        return "fake"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {}

    def _consume_text_steps(self) -> list[str]:
        text_steps = []
        while self._index < len(self.steps) and isinstance(
            self.steps[self._index], AssistantReply
        ):
            text_steps.append(self.steps[self._index].text)
            self._index += 1
        return text_steps

    def _next_tool_call(self) -> AIMessageChunk:
        item = self.steps[self._index]
        self._index += 1
        return AIMessageChunk(
            content="",
            tool_call_chunks=[
                {
                    "id": item.id,
                    "name": item.name,
                    "args": item.args,
                    "index": 0,
                }
            ],
        )


class FakeChannel(BaseChannel):
    async def start_conversation(
        self,
        session_id: uuid.UUID,
        channel_internal_id: int,
        new_messages: list[AgentMessage] | None = None,
        agent: Agent | None = None,
    ):
        await self._generate_and_send_answer(
            session_id=session_id,
            agent=agent,
            new_messages=new_messages or [],
        )

    async def _generate_and_send_answer(
        self,
        session_id: uuid.UUID,
        agent: Agent | None = None,
        new_messages: tuple = (),
    ):
        agent = agent or self._agent

        for msg in new_messages:
            await self._sessions_storage.add_message(
                session_id=session_id,
                message=msg,
            )

        message_generator = self._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_id)
        )
        history = [msg async for msg in message_generator]

        with self.set_current_channel():
            if await agent.has_pending_interrupt(session_id=session_id):
                async for _ in agent.resume_after_confirmation(
                    session_id=session_id,
                    decision=DecisionEnum.REJECT,
                    new_messages=new_messages,
                ):
                    pass
            else:
                async for _ in agent.ask(messages=history):
                    pass
