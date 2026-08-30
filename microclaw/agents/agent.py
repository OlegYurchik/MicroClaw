from collections.abc import AsyncGenerator, Sequence
import contextlib
import datetime
import json
import pathlib
import traceback
from typing import Any
import uuid

from .checkpointer import SyncerCheckpointer
from .dto import (
    AgentPromptValues,
    SummaryMemoryValues,
    SummaryValues,
    SystemValues,
)
from deepagents import create_deep_agent
import deepagents.graph
from evolution_langchain import EvolutionInference
from jinja2 import Template
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
)
from langchain.messages import ToolMessage
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.runnables import RunnableLambda
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphBubbleUp
from langgraph.types import Command
from loguru import logger
import tiktoken

from microclaw.agents.settings import (
    AgentSettings,
    APITypeEnum,
    MCPLocalSettings,
    MCPRemoteSettings,
    MCPSettings,
    ModelSettings,
    ProviderSettings,
)
from microclaw.dto import AgentMessage, DecisionEnum, InterruptEntry, Spending
from microclaw.syncers import SyncerInterface
from microclaw.toolkits import BaseToolKit
from microclaw.toolkits.memory import MemoryToolKit
from microclaw.utils.context import (
    get_current_request_id,
    get_current_session_id,
)


class _NoOpMiddleware(AgentMiddleware):
    name = "SummarizationMiddleware"


@contextlib.contextmanager
def _patched_summarization_middleware():
    original = deepagents.graph.create_summarization_middleware
    deepagents.graph.create_summarization_middleware = lambda *args, **kwargs: (
        _NoOpMiddleware()
    )
    try:
        yield
    finally:
        deepagents.graph.create_summarization_middleware = original


class Agent:
    TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
    RECURSION_LIMIT = 1000
    TOOL_OUTPUT_TRUNCATION_RATIO = 2

    _template_cache: dict[str, Template] = {}

    def __init__(
        self,
        settings: AgentSettings,
        model_settings: ModelSettings,
        provider_settings: ProviderSettings,
        toolkits: dict[str, BaseToolKit],
        syncer: SyncerInterface,
        mcp_settings: dict[str, MCPSettings] | None = None,
        subagents: list["Agent"] | None = None,
        client=None,
        skills: list[str] | None = None,
    ):
        self._settings = settings
        self._model_settings = model_settings
        self._provider_settings = provider_settings
        self._toolkits = toolkits
        self._skills = skills or []
        self._checkpointer = SyncerCheckpointer(syncer)

        self._memory_toolkit = None
        for toolkit in toolkits.values():
            if isinstance(toolkit, MemoryToolKit):
                self._memory_toolkit = toolkit
                break

        self._mcp_settings = mcp_settings or {}
        self._mcp = self._create_mcp_client()
        self._subagents = subagents.copy() if subagents else []
        self._tools = [
            tool for toolkit in self._toolkits.values() for tool in toolkit.get_tools()
        ]
        self._client = client or self.get_client()

    @property
    def toolkits(self) -> dict[str, "BaseToolKit"]:
        return self._toolkits

    @property
    def settings(self) -> AgentSettings:
        return self._settings

    def _create_mcp_client(self) -> MultiServerMCPClient:
        servers = {}
        for settings in self._mcp_settings.values():
            if isinstance(settings, MCPRemoteSettings):
                server_name = settings.name or settings.url
                mcp_data = {}
                if settings.url.startswith("http"):
                    mcp_data["transport"] = "http"
                elif settings.url.startswith("ws"):
                    mcp_data["transport"] = "ws"
                else:
                    raise ValueError(f"Incorrect MCP URL: {settings.url}")
                mcp_data["url"] = settings.url
                mcp_data["headers"] = settings.headers or {}
            elif isinstance(settings, MCPLocalSettings):
                server_name = settings.name or " ".join(
                    (settings.command, *settings.args)
                )
                mcp_data = {
                    "transport": "stdio",
                    "command": settings.command,
                    "args": settings.args,
                }
                mcp_data["env"] = settings.env or {}
            else:
                raise ValueError(f"Unsupported MCP settings type: {type(settings)}")
            servers[server_name] = mcp_data

        return MultiServerMCPClient(servers)

    @property
    def name(self) -> str:
        return self._settings.identity.name if self._settings.identity else ""

    @property
    def description(self) -> str | None:
        return self._settings.identity.description if self._settings.identity else None

    def as_subagent(self) -> dict:
        async def _runnable(input_data: dict) -> dict:
            messages = input_data.get("messages", [])
            agent_messages = []
            for msg in messages:
                role = "user"
                if isinstance(msg, HumanMessage):
                    role = "user"
                elif isinstance(msg, AIMessage):
                    role = "assistant"
                elif isinstance(msg, SystemMessage):
                    role = "system"
                elif isinstance(msg, ToolMessage):
                    role = "tool"
                text = msg.content if isinstance(msg.content, str) else str(msg.content)
                agent_messages.append(AgentMessage(role=role, text=text))

            try:
                last_text: str | None = None
                total_spending: Spending | None = None
                async for msg in self.ask(agent_messages, stream=False):
                    if msg.spending:
                        if total_spending is None:
                            total_spending = msg.spending
                        else:
                            total_spending += msg.spending
                    if msg.role == "assistant" and msg.text:
                        last_text = msg.text
                final_text = last_text or ""
            except Exception as exc:
                logger.opt(exception=True).error("Subagent {} failed", self.name)
                final_text = f"Subagent error: {exc}"

            result: dict[str, Any] = {"messages": [AIMessage(content=final_text)]}
            if total_spending is not None:
                result["spending"] = total_spending.model_dump(mode="json")
            return result

        return {
            "name": self.name,
            "description": self.description or f"Subagent: {self.name}",
            "runnable": RunnableLambda(_runnable),
        }

    def set_subagents(self, subagents: list["Agent"] | None):
        self._subagents = subagents.copy() if subagents else []

    def get_client(self):
        api_type = self._model_settings.api_type or self._provider_settings.api_type
        api_key = self._model_settings.api_key or self._provider_settings.api_key
        base_url = str(self._provider_settings.base_url)
        default_headers = self._provider_settings.headers | self._model_settings.headers
        temperature = (
            self._settings.temperature or self._model_settings.temperature or 1
        )

        match api_type:
            case APITypeEnum.OPENAI:
                if not api_key:
                    raise ValueError("API key for OpenAI not provided")
                return ChatOpenAI(
                    model=self._model_settings.id,
                    api_key=api_key,
                    base_url=base_url
                    if base_url != "https://api.openai.com/v1"
                    else None,
                    default_headers=default_headers,
                    temperature=temperature,
                )
            case APITypeEnum.CLOUDRU:
                if not api_key:
                    raise ValueError("API key for Cloud.ru not provided")
                key_id, key_secret = api_key.split(":")
                return EvolutionInference(
                    model=self._model_settings.id,
                    key_id=key_id,
                    secret=key_secret,
                    base_url=(
                        base_url
                        if base_url != "https://foundation-models.api.cloud.ru/v1"
                        else None
                    ),
                    temperature=temperature,
                )
            case APITypeEnum.OLLAMA:
                return ChatOllama(
                    model=self._model_settings.id,
                    base_url=base_url if base_url != "http://localhost:11434" else None,
                    temperature=temperature,
                )
            case _:
                raise ValueError(f"Unsupported API type: '{api_type.value}'")

    async def ask(
        self,
        messages: list[AgentMessage],
        channel: "BaseChannel | None" = None,  # noqa: F821
        stream: bool = False,
    ) -> AsyncGenerator[AgentMessage, None]:
        session_id = get_current_session_id()
        request_id = get_current_request_id()
        bound_logger = logger.bind(request_id=request_id, session_id=session_id)
        langchain_messages: list[BaseMessage] = self._convert_to_langchain_messages(
            messages
        )
        system_prompt = await self._get_agent_prompt(channel=channel)

        bound_logger.info(
            "Agent ask started",
            messages_count=len(messages),
            tools_count=len(self._tools),
        )

        if session_id is not None:
            await self._checkpointer.adelete_thread(str(session_id))

        agent = await self._create_agent(
            channel=channel,
            system_prompt=system_prompt,
            bound_logger=bound_logger,
        )

        config = {
            "recursion_limit": self.RECURSION_LIMIT,
            "configurable": {"thread_id": str(session_id or "")},
        }

        events_generator = self._process_astream(
            agent,
            {"messages": langchain_messages},
            config,
            bound_logger,
            stream,
            initial_messages=messages,
        )

        async for msg in events_generator:
            yield msg

        bound_logger.info("Agent ask finished")

    async def resume_after_confirmation(
        self,
        session_id: uuid.UUID,
        decision: DecisionEnum,
        new_messages: Sequence[AgentMessage] = (),
        channel: "BaseChannel | None" = None,  # noqa: F821
    ) -> AsyncGenerator[AgentMessage, None]:
        request_id = get_current_request_id()
        bound_logger = logger.bind(request_id=request_id, session_id=session_id)
        bound_logger.info(
            "Agent resume_after_confirmation started",
            decision=decision.value,
        )

        system_prompt = await self._get_agent_prompt(channel=channel)
        agent = await self._create_agent(
            channel=channel,
            system_prompt=system_prompt,
            bound_logger=bound_logger,
        )

        config = {
            "recursion_limit": self.RECURSION_LIMIT,
            "configurable": {"thread_id": str(session_id)},
        }

        langchain_messages = self._convert_to_langchain_messages(new_messages)
        input_data = Command(
            resume=decision.value,
            update={"messages": langchain_messages},
        )

        events_generator = self._process_astream(
            agent,
            input_data,
            config,
            bound_logger,
            stream=False,
            initial_messages=new_messages,
        )

        async for msg in events_generator:
            yield msg

    async def has_pending_interrupt(self, session_id: uuid.UUID) -> bool:
        config = {
            "configurable": {"thread_id": str(session_id)},
        }
        try:
            checkpoint = await self._checkpointer.aget_tuple(config)
        except (KeyError, ValueError, TypeError):
            return False
        if checkpoint is None or not checkpoint.pending_writes:
            return False
        return any(
            channel == "__interrupt__"
            for _task_id, channel, _value in checkpoint.pending_writes
        )

    async def _create_agent(
        self,
        channel: "BaseChannel | None",  # noqa: F821
        system_prompt: str,
        bound_logger=logger,
    ):
        mcp_tools = []
        for server_name in self._mcp.connections:
            try:
                server_tools = list(
                    await self._mcp.get_tools(server_name=server_name)
                )
                mcp_tools.extend(server_tools)
                bound_logger.info(
                    "Loaded {} MCP tools from {}",
                    len(server_tools),
                    server_name,
                )
            except Exception as exception:
                bound_logger.warning(
                    "Cannot load MCP tools from {}: {}",
                    server_name,
                    exception,
                )

        tools = list(self._tools) + mcp_tools
        if channel is not None:
            channel_toolkit = channel.get_toolkit()
            if channel_toolkit is not None:
                tools.extend(channel_toolkit.get_tools())
        subagent_specs = [subagent.as_subagent() for subagent in self._subagents]
        tool_call_limiter = ToolCallLimitMiddleware(
            run_limit=self._settings.max_tool_calls,
            exit_behavior="end",
        )
        model_call_limiter = ModelCallLimitMiddleware(
            run_limit=self._settings.max_model_calls,
            exit_behavior="end",
        )
        model_retry = ModelRetryMiddleware(
            max_retries=self._settings.model_max_retries,
            backoff_factor=self._settings.model_retry_backoff_factor,
            initial_delay=self._settings.model_retry_initial_delay,
        )

        with _patched_summarization_middleware():
            agent = create_deep_agent(
                model=self._client,
                tools=tools,
                system_prompt=system_prompt,
                subagents=subagent_specs,
                middleware=[
                    _handle_tool_errors,
                    _disable_parallel_tool_calls,
                    model_retry,
                    tool_call_limiter,
                    model_call_limiter,
                ],
                skills=self._skills,
                checkpointer=self._checkpointer,
            )

        return agent

    async def _process_astream(
        self,
        agent,
        input_data: dict | Command,
        config: dict,
        bound_logger,
        stream: bool,
        initial_messages: list[AgentMessage] | None = None,
    ) -> AsyncGenerator[AgentMessage, None]:
        session_id = get_current_session_id()
        spending = self._get_empty_spending()
        accumulated_message: AgentMessage | None = None
        current_chunked_message_id: str | None = None

        async for namespace, stream_mode, chunk in agent.astream(
            input_data,
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            if namespace:
                continue

            match stream_mode:
                case "messages":
                    msg_chunk, metadata = chunk
                    if not hasattr(msg_chunk, "content") or not msg_chunk.content:
                        continue

                    chunk_role = self._detect_chunk_role(msg_chunk)

                    if chunk_role == "tool":
                        continue

                    text = self._convert_content_to_text(msg_chunk.content)
                    if not text:
                        continue

                    if accumulated_message is None:
                        current_chunked_message_id = str(uuid.uuid4())
                        accumulated_message = AgentMessage(
                            role="assistant",
                            chunked_message_id=current_chunked_message_id,
                            text="",
                        )
                        if initial_messages:
                            spending.input_tokens += sum(
                                self._get_tokens_count(m.text)
                                for m in initial_messages
                                if m.text
                            )

                    accumulated_message.text += text
                    spending.output_tokens += self._get_tokens_count(text)

                    if stream:
                        yield AgentMessage(
                            role="assistant",
                            text=text,
                            chunked_message_id=current_chunked_message_id,
                        )

                case "updates":
                    update_data = chunk

                    if "__interrupt__" in update_data:
                        interrupts = update_data["__interrupt__"]
                        entries = []
                        for intr in interrupts:
                            val = intr.value
                            description = (
                                val.get("description", str(val))
                                if isinstance(val, dict)
                                else str(val)
                            )
                            entries.append(
                                InterruptEntry(
                                    id=intr.id,
                                    value=val,
                                    description=description,
                                    session_id=str(session_id) if session_id else None,
                                )
                            )
                        yield AgentMessage(
                            role="request_confirmation",
                            text=json.dumps(
                                [e.model_dump() for e in entries], default=str
                            ),
                        )
                        return

                    for node_name, node_data in update_data.items():
                        if (
                            not isinstance(node_data, dict)
                            or "messages" not in node_data
                        ):
                            continue
                        subagent_spending = self._extract_subagent_spending(
                            node_data
                        )
                        if subagent_spending is not None:
                            spending += subagent_spending
                        for msg in node_data["messages"]:
                            if getattr(msg, "type", None) == "tool":
                                tool_content = (
                                    self._convert_content_to_text(msg.content) or ""
                                )
                                compact = self._compact_tool_output(tool_content)
                                is_error = getattr(msg, "status", None) == "error"
                                tool_name = getattr(msg, "name", "unknown")
                                if is_error:
                                    yield AgentMessage(
                                        role="tool",
                                        text=json.dumps(
                                            {
                                                "type": "error",
                                                "name": tool_name,
                                                "error": compact,
                                            },
                                            ensure_ascii=False,
                                        ),
                                    )
                                else:
                                    yield AgentMessage(
                                        role="tool",
                                        text=json.dumps(
                                            {
                                                "type": "output",
                                                "name": tool_name,
                                                "content": compact,
                                            },
                                            ensure_ascii=False,
                                        ),
                                    )
                            elif (
                                getattr(msg, "type", None) == "ai"
                                and hasattr(msg, "tool_calls")
                                and msg.tool_calls
                            ):
                                for tc in msg.tool_calls:
                                    yield AgentMessage(
                                        role="tool",
                                        text=json.dumps(
                                            {
                                                "type": "input",
                                                "name": tc.get("name", "unknown"),
                                                "args": tc.get("args", {}),
                                            },
                                            ensure_ascii=False,
                                            default=str,
                                        ),
                                    )

                    if not stream and accumulated_message:
                        yield accumulated_message
                        accumulated_message = None

        if (
            accumulated_message is None
            and spending.input_tokens
            and not spending.output_tokens
        ):
            logger.warning(
                "Model returned no content after processing "
                f"(input_tokens={spending.input_tokens}). "
                "This may be a thinking-only response."
            )

        if self._model_settings.costs:
            spending.calculate_cost(model_costs=self._model_settings.costs)

        if spending.input_tokens or spending.output_tokens:
            yield AgentMessage(
                role="assistant",
                spending=spending,
                context_tokens=spending.input_tokens + spending.output_tokens or None,
            )

    async def summarize_memory(
        self,
        new_context: str,
        old_context: str,
        max_tokens: int = 300,
        is_daily: bool = False,
    ) -> AgentMessage:
        summary_prompt = self._get_summary_memory_prompt(
            old_context=old_context,
            new_context=new_context,
            max_tokens=max_tokens,
            is_daily=is_daily,
        )
        summary_messages = [
            SystemMessage(content="You are an expert at summarizing memory content."),
            HumanMessage(content=summary_prompt),
        ]
        response = await self._client.ainvoke(summary_messages)

        spending = self._get_empty_spending()
        spending.input_tokens = sum(
            self._get_tokens_count(text=message.content) for message in summary_messages
        )
        spending.output_tokens = self._get_tokens_count(text=response.content)
        if self._model_settings.costs is not None:
            spending.calculate_cost(model_costs=self._model_settings.costs)

        return AgentMessage(
            role="summary",
            text=response.content,
            spending=spending,
        )

    async def summarize_dialogue(
        self,
        messages: list[AgentMessage],
        max_tokens: int = 300,
    ) -> AgentMessage:
        if not messages:
            return AgentMessage(
                role="summary",
                text="Dialog is empty",
            )

        summary_prompt = self._get_summary_dialogue_prompt(
            messages=messages,
            max_tokens=max_tokens,
        )
        summary_messages = [
            SystemMessage(content="You are an expert in dialogue summarization."),
            HumanMessage(content=summary_prompt),
        ]

        response = await self._client.ainvoke(summary_messages)

        spending = self._get_empty_spending()
        spending.input_tokens = sum(
            self._get_tokens_count(text=message.content) for message in summary_messages
        )
        spending.output_tokens = self._get_tokens_count(text=response.content)
        if self._model_settings.costs is not None:
            spending.calculate_cost(model_costs=self._model_settings.costs)

        return AgentMessage(
            role="summary",
            text=f"Summary of the previous dialogue:\n{response.content}",
            spending=spending,
        )

    async def extract_important_info(
        self,
        messages: list[AgentMessage],
        max_tokens: int = 300,
        is_daily: bool = False,
    ) -> str:
        system_prompt = (
            "You are an expert at extracting current context information from dialogues."
            if is_daily
            else "You are an expert at extracting long-term important information from dialogues."
        )
        user_prompt = self._get_extract_dialogue_info_prompt(
            messages=messages,
            max_tokens=max_tokens,
            is_daily=is_daily,
        )

        extract_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = await self._client.ainvoke(extract_messages)
        return response.content.strip()

    def get_model_context_window_size(self) -> int | None:
        if self._model_settings.context_window_size is not None:
            return self._model_settings.context_window_size

        if hasattr(self._client, "profile") and self._client.profile:
            max_input_tokens = self._client.profile.get("max_input_tokens")
            if max_input_tokens:
                return max_input_tokens

        model_name = (
            getattr(self._client, "model_name", None) or self._model_settings.id
        )

        if hasattr(self._client, "modelname_to_contextsize"):
            return self._client.modelname_to_contextsize(model_name)
        if hasattr(self._client, "max_context_length"):
            return self._client.max_context_length
        if hasattr(self._client, "context_window"):
            return self._client.context_window

    def get_context_threshold_size(self) -> float | None:
        return self._model_settings.context_threshold_size

    def is_summarization_enabled(self) -> bool:
        return self._settings.enable_summarization

    def is_memory_flush_enabled(self) -> bool:
        return self._settings.enable_memory_flush

    def get_max_memory_flush_tokens(self) -> int:
        return self._settings.max_memory_flush_tokens

    def get_memory_toolkit(self) -> MemoryToolKit | None:
        return self._memory_toolkit

    def _convert_content_to_text(self, content) -> str | None:
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            return "\n\n".join(
                content_part.get("text", "")
                for content_part in content
                if content_part.get("type") == "text"
            )

    def _detect_chunk_role(self, msg_chunk) -> str:
        if (
            getattr(msg_chunk, "type", None) == "tool"
            or (hasattr(msg_chunk, "tool_calls") and msg_chunk.tool_calls)
            or (hasattr(msg_chunk, "tool_call_chunks") and msg_chunk.tool_call_chunks)
        ):
            return "tool"

        return "assistant"

    def _get_tokens_count(self, text: str) -> int:
        if len(text) == 0:
            return 0

        try:
            tokenizer = tiktoken.encoding_for_model(self._model_settings.id)
        except KeyError:
            tokenizer = tiktoken.get_encoding("cl100k_base")

        return len(tokenizer.encode(text))

    async def _get_agent_prompt(
        self,
        channel: "BaseChannel | None" = None,  # noqa: F821
    ) -> str:
        template = self._get_cached_template("agent_prompt.j2")

        toolkits = dict(self._toolkits)
        tools = list(self._tools)
        if channel is not None:
            channel_toolkit = channel.get_toolkit()
            if channel_toolkit is not None:
                toolkits["channel"] = channel_toolkit
                tools.extend(channel_toolkit.get_tools())

        memories = await self._get_memory_context()
        agent_prompt_values = AgentPromptValues(
            agent_identity=self._settings.identity,
            system=SystemValues(time=datetime.datetime.now(datetime.timezone.utc)),
            max_tool_calls=self._settings.max_tool_calls,
            toolkits=toolkits,
            tools=tools,
            channel=channel,
            memories=memories,
        )

        prompt = template.render(data=agent_prompt_values)
        return prompt

    async def _get_memory_context(self) -> dict[str, str] | None:
        memory_toolkit = self._toolkits.get("memory")
        if not memory_toolkit or not hasattr(memory_toolkit, "get_memory"):
            return None

        memories = {}
        general_memory = await memory_toolkit.get_memory(date=None)
        if general_memory and general_memory.strip():
            memories["General Memory"] = general_memory.strip()

        today = datetime.date.today()
        today_memory = await memory_toolkit.get_memory(date=today)
        if today_memory and today_memory.strip():
            memories[f"Today's Memory ({today})"] = today_memory.strip()

        yesterday = today - datetime.timedelta(days=1)
        yesterday_memory = await memory_toolkit.get_memory(date=yesterday)
        if yesterday_memory and yesterday_memory.strip():
            memories[f"Yesterday's Memory ({yesterday})"] = yesterday_memory

        return memories

    def _get_summary_memory_prompt(
        self,
        old_context: str,
        new_context: str,
        max_tokens: int = 300,
        is_daily: bool = False,
    ) -> str:
        template_name = (
            "summarize_memory_daily_prompt.j2"
            if is_daily
            else "summarize_memory_prompt.j2"
        )
        template = self._get_cached_template(template_name)

        data = SummaryMemoryValues(
            old_context=old_context,
            new_context=new_context,
            max_tokens=max_tokens,
        )

        prompt = template.render(data=data)
        return prompt

    def _get_summary_dialogue_prompt(
        self,
        messages: list[AgentMessage],
        max_tokens: int = 300,
    ) -> str:
        template = self._get_cached_template("summarize_dialogue_prompt.j2")

        context = "\n".join(
            f"{message.role}: {message.text}"
            for message in messages
            if message.text and message.text.strip()
        )
        data = SummaryValues(
            context=context,
            max_tokens=max_tokens,
        )

        prompt = template.render(data=data)
        return prompt

    def _get_extract_dialogue_info_prompt(
        self,
        messages: list[AgentMessage],
        max_tokens: int = 300,
        is_daily: bool = False,
    ) -> str:
        template_name = (
            "extract_dialogue_info_daily_prompt.j2"
            if is_daily
            else "extract_dialogue_info_prompt.j2"
        )
        template = self._get_cached_template(template_name)

        context = "\n".join(
            f"{message.role}: {message.text}"
            for message in messages
            if message.text and message.text.strip()
        )
        data = SummaryValues(
            context=context,
            max_tokens=max_tokens,
        )

        prompt = template.render(data=data)
        return prompt

    @classmethod
    def _get_cached_template(cls, name: str) -> Template:
        if name not in cls._template_cache:
            template_path = cls.TEMPLATES_DIR / name
            cls._template_cache[name] = Template(template_path.read_text())
        return cls._template_cache[name]

    def _get_empty_spending(self) -> Spending:
        return Spending(
            currency=(
                self._model_settings.costs.currency
                if self._model_settings.costs is not None
                else "$"
            ),
        )

    def _compact_tool_output(self, output: Any) -> str:
        max_len = self._settings.max_tool_output_chars

        if output is None:
            return "None"

        if isinstance(output, (dict, list)):
            try:
                text = json.dumps(output, ensure_ascii=False, indent=2, default=str)
            except Exception:
                text = str(output)
        else:
            text = str(output)

        if len(text) <= max_len:
            return text

        separator = f"\n\n...[truncated, {len(text)} chars total]...\n\n"
        half = max(
            (max_len - len(separator)) // self.TOOL_OUTPUT_TRUNCATION_RATIO, 0
        )
        return text[:half] + separator + text[-half:]

    def _extract_subagent_spending(self, tool_output: Any) -> Spending | None:
        spending_data = None

        if isinstance(tool_output, dict):
            spending_data = tool_output.get("spending")
        elif isinstance(tool_output, list):
            for message in tool_output:
                if isinstance(message, dict):
                    sd = message.get("spending")
                    if sd:
                        spending_data = sd
                        break

        if not isinstance(spending_data, dict):
            return None

        try:
            return Spending(**spending_data)
        except (TypeError, ValueError):
            return None

    def _convert_to_langchain_messages(
        self, messages: Sequence[AgentMessage]
    ) -> list[BaseMessage]:
        langchain_messages = []
        for agent_message in messages:
            if agent_message.text is None:
                continue
            if agent_message.role == "tool":
                continue
            langchain_message = None
            match agent_message.role:
                case "system":
                    langchain_message = SystemMessage(content=agent_message.text)
                case "summary":
                    langchain_message = HumanMessage(content=agent_message.text)
                case "user":
                    langchain_message = HumanMessage(content=agent_message.text)
                case "assistant":
                    langchain_message = AIMessage(content=agent_message.text)
                case _:
                    langchain_message = HumanMessage(content=agent_message.text)
            langchain_messages.append(langchain_message)
        return langchain_messages


@wrap_tool_call
async def _handle_tool_errors(request, handler) -> Any:
    try:
        return await handler(request)
    except GraphBubbleUp as exception:
        raise exception
    except Exception as exception:
        tb = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            ),
        )
        return ToolMessage(
            content=f"Tool error: {exception}\n\nTraceback:\n{tb}",
            tool_call_id=request.tool_call["id"],
            name=request.tool_call.get("name"),
        )


@wrap_model_call
async def _disable_parallel_tool_calls(request: ModelRequest, handler) -> Any:
    request = request.override(model_settings={"parallel_tool_calls": False})
    return await handler(request)
