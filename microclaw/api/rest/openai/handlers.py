import contextlib
from typing import Any
import uuid

from microclaw.api.rest.exceptions import HTTPBadRequest, HTTPNotFound
from microclaw.api.rest.openai.adapter import OpenAIMessageAdapter
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import DecisionEnum
from microclaw.resolver import DependencyResolver
from microclaw.sessions_storages.dto import SessionCreate
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.sessions_storages.utils import get_messages_from_last_summarization
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.utils.context import (
    REQUEST_ID_CONTEXT,
    SESSION_ID_CONTEXT,
)


@contextlib.asynccontextmanager
async def _rest_context(
        session_id: uuid.UUID,
        request_id: uuid.UUID,
):
    session_token = SESSION_ID_CONTEXT.set(session_id)
    request_token = REQUEST_ID_CONTEXT.set(request_id)
    toolkit_token = _set_toolkit_context(session_id, request_id)
    try:
        yield
    finally:
        TOOLKIT_CONTEXT.reset(toolkit_token)
        SESSION_ID_CONTEXT.reset(session_token)
        REQUEST_ID_CONTEXT.reset(request_token)


def _set_toolkit_context(session_id: uuid.UUID, request_id: uuid.UUID):
    context = ToolkitExecutionContext(
        session_id=session_id,
        request_id=request_id,
        channel_key="rest",
        channel_internal_id=str(request_id),
    )
    return TOOLKIT_CONTEXT.set(context)


async def run_completion(
        model: str,
        messages: list[dict],
        body: dict,
        resolver: DependencyResolver,
        sessions_storage: SessionsStorageInterface,
) -> Any:
    metadata = body.get("metadata", {})
    session_id_str = metadata.get("session_id")
    stream = body.get("stream", False)
    decision = metadata.get("decision")

    agents = await resolver.resolve_agents()
    agent = agents.get(model)
    if agent is None:
        raise HTTPNotFound(detail=f"Agent {model} not found")

    if session_id_str:
        try:
            session_id = uuid.UUID(session_id_str)
        except ValueError as exc:
            raise HTTPBadRequest(
                detail="Invalid session_id",
            ) from exc
    else:
        session = await sessions_storage.create_session(
            data=SessionCreate(
                channel_key="rest",
                channel_internal_id=str(uuid.uuid4()),
            )
        )
        session_id = session.id

    history = []
    async for message in get_messages_from_last_summarization(
        storage=sessions_storage,
        session_id=session_id,
    ):
        history.append(message)
    new_messages = [OpenAIMessageAdapter.to_agent_message(m) for m in messages]
    all_messages = history + new_messages

    request_id = uuid.uuid4()
    saver = AgentMessageSaver(sessions_storage=sessions_storage, session_id=session_id)

    if decision is not None:
        try:
            decision_enum = DecisionEnum(decision)
        except ValueError as exc:
            raise HTTPBadRequest(
                detail=f"Invalid decision: {decision}. Must be 'approve' or 'reject'.",
            ) from exc
    else:
        decision_enum = None

    has_interrupt = decision_enum and await agent.has_pending_interrupt(session_id)
    if has_interrupt:
        gen = agent.resume_after_confirmation(
            session_id=session_id,
            decision=decision_enum,
            new_messages=new_messages,
        )
    elif stream:
        gen = agent.ask(messages=all_messages, stream=True)
    else:
        gen = agent.ask(messages=all_messages, stream=False)

    if stream:
        return _stream(gen, saver, session_id, request_id)

    return await _sync(gen, saver, session_id, request_id)


def list_models(resolver: DependencyResolver) -> list[str]:
    return list(resolver.settings.agents.keys())


async def _sync(
        gen,
        saver: AgentMessageSaver,
        session_id: uuid.UUID,
        request_id: uuid.UUID,
) -> str:
    result_text = ""
    async with _rest_context(session_id, request_id), saver:
        async for msg in gen:
            await saver.register_new_message(msg)
            if msg.text:
                result_text += msg.text
    return result_text


async def _stream(
        gen,
        saver: AgentMessageSaver,
        session_id: uuid.UUID,
        request_id: uuid.UUID,
):
    async with _rest_context(session_id, request_id), saver:
        async for msg in gen:
            await saver.register_new_message(msg)
            if msg.text:
                yield msg.text
