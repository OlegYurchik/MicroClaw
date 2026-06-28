import contextlib
import datetime
import json
import logging
import pathlib
import traceback
import uuid
from typing import Any, AsyncGenerator

import deepagents.graph
import tiktoken
from evolution_langchain import EvolutionInference
from jinja2 import Template
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.runnables import RunnableLambda
from deepagents import create_deep_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain.messages import ToolMessage

from microclaw.agents.settings import (
    AgentSettings,
    ModelSettings,
    ProviderSettings,
    APITypeEnum,
    MCPLocalSettings,
    MCPRemoteSettings,
    MCPSettings,
)
from microclaw.dto import AgentMessage, Spending
from microclaw.toolkits import BaseToolKit
from microclaw.toolkits.memory import MemoryToolKit
from .dto import SummaryValues, SummaryMemoryValues, AgentPromptValues, SystemValues, MCPInfo


class _NoOpMiddleware(AgentMiddleware):
    name = "SummarizationMiddleware"


@contextlib.contextmanager
def _patched_summarization_middleware():
    original = deepagents.graph.create_summarization_middleware
    deepagents.graph.create_summarization_middleware = lambda *args, **kwargs: _NoOpMiddleware()
    try:
        yield
    finally:
        deepagents.graph.create_summarization_middleware = original


logger = logging.getLogger(__name__)


class Agent:
    TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"

    def __init__(
            self,
            settings: AgentSettings,
            model_settings: ModelSettings,
            provider_settings: ProviderSettings,
            toolkits: dict[str, BaseToolKit],
            mcp_settings: dict[str, MCPSettings] | None = None,
            subagents: list["Agent"] | None = None,
            client=None,
    ):
        self._settings = settings
        self._model_settings = model_settings
        self._provider_settings = provider_settings
        self._toolkits = toolkits

        self._memory_toolkit = None
        for toolkit in toolkits.values():
            if isinstance(toolkit, MemoryToolKit):
                self._memory_toolkit = toolkit
                break

        self._mcp_settings = mcp_settings or {}
        self._mcp = self._create_mcp_client()
        self._subagents = subagents.copy() if subagents else []
        self._tools = [
            tool
            for toolkit in self._toolkits.values()
            for tool in toolkit.get_tools()
        ]
        self._client = client or self.get_client()

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
            elif isinstance(settings, MCPLocalSettings):
                server_name = settings.name or " ".join((settings.command, *settings.args))
                mcp_data = {
                    "transport": "stdio",
                    "command": settings.command,
                    "args": settings.args,
                }
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
        """
        Превращает текущий объект Agent в CompiledSubAgent для использования
        в родительском агенте DeepAgents.
        """
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
                async for msg in self.ask(agent_messages, stream=False):
                    if msg.role == "assistant" and msg.text:
                        last_text = msg.text
                final_text = last_text or ""
            except Exception as exc:
                final_text = f"Subagent error: {exc}"

            return {"messages": [AIMessage(content=final_text)]}

        return {
            "name": self.name,
            "description": self.description or f"Subagent: {self.name}",
            "runnable": RunnableLambda(_runnable),
        }

    def set_subagents(self, subagents: list["Agent"]):
        self._subagents = subagents.copy()

    def get_client(self):
        api_type = self._model_settings.api_type or self._provider_settings.api_type
        api_key = self._model_settings.api_key or self._provider_settings.api_key
        base_url = str(self._provider_settings.base_url)
        default_headers = self._provider_settings.headers | self._model_settings.headers
        temperature = self._settings.temperature or self._model_settings.temperature or 1

        match api_type:
            case APITypeEnum.OPENAI:
                if not api_key:
                    raise ValueError("API key for OpenAI not provided")
                return ChatOpenAI(
                    model=self._model_settings.id,
                    api_key=api_key,
                    base_url=base_url if base_url != "https://api.openai.com/v1" else None,
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
    ) -> AsyncGenerator[AgentMessage]:
        from microclaw.channels import BaseChannel

        request_id = BaseChannel.get_current_request_id()
        langchain_messages: list[BaseMessage] = self._convert_to_langchain_messages(messages)
        system_prompt = await self._get_agent_prompt(channel=channel)

        logger.info(
            "[%s] Agent ask started messages_count=%s tools_count=%s",
            request_id, len(messages), len(self._tools),
        )

        mcp_tools = []
        try:
            mcp_tools = list(await self._mcp.get_tools())
        except Exception as e:
            pass

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
        config = {"recursion_limit": 1000}

        with _patched_summarization_middleware():
            agent = create_deep_agent(
                model=self._client,
                tools=tools,
                system_prompt=system_prompt,
                subagents=subagent_specs,
                middleware=[_handle_tool_errors, tool_call_limiter, model_call_limiter],
            )

        events_generator = agent.astream_events(
            {"messages": langchain_messages},
            config=config,
            version="v2",
        )

        spending = self._get_empty_spending()
        accumulated_message: AgentMessage | None = None
        current_chunked_message_id: str | None = None

        async for event in events_generator:
            event_type = event["event"]
            match event_type:
                case "on_chat_model_start":
                    current_chunked_message_id = str(uuid.uuid4())
                    accumulated_message = AgentMessage(
                        role="assistant",
                        chunked_message_id=current_chunked_message_id,
                    )
                    spending = self._get_empty_spending()
                    spending.input_tokens += sum(
                        self._get_tokens_count(text=message.text)
                        for message in messages
                        if message.text
                    )
                case "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    text = self._convert_content_to_text(chunk.content)
                    if not text:
                        continue
                    spending.output_tokens += self._get_tokens_count(text=text)
                    message = AgentMessage(
                        role="assistant",
                        text=text,
                        chunked_message_id=current_chunked_message_id,
                    )
                    if stream:
                        yield message
                    else:
                        accumulated_message.text = (accumulated_message.text or "") + message.text
                case "on_chat_model_end":
                    output = event["data"]["output"]
                    # TODO: Enable later
                    if False and (usage_metadata := getattr(output, "usage_metadata", None)):
                        spending.input_tokens = usage_metadata.get("input_tokens", spending.input_tokens)
                        spending.output_tokens = usage_metadata.get("output_tokens", spending.output_tokens)
                        spending.cache_read_tokens = usage_metadata.get("cache_read_tokens", spending.cache_read_tokens)
                        spending.cache_write_tokens = usage_metadata.get("cache_write_tokens", spending.cache_write_tokens)
                    # TODO: Enable leter
                    elif (
                            False and
                            (response_metadata := getattr(output, "response_metadata", None)) and
                            (token_usage := response_metadata.get("token_usage"))
                    ):
                        spending.input_tokens = token_usage.get("prompt_tokens", 0)
                        spending.output_tokens = token_usage.get("completion_tokens", 0)
                    else:
                        text = self._convert_content_to_text(output.content)
                        if text is not None:
                            spending.output_tokens = self._get_tokens_count(text)
                    if self._model_settings.costs is not None:
                        spending.calculate_cost(model_costs=self._model_settings.costs)
                    if not stream and accumulated_message:
                        yield accumulated_message
                        accumulated_message = None

                    yield AgentMessage(
                        role="assistant",
                        spending=spending,
                    )
                    spending = self._get_empty_spending()
                case "on_tool_start":
                    tool_name = event["name"]
                    logger.info("[%s] Tool call started tool=%s", request_id, tool_name)
                    tool_input = event["data"].get("input", {})
                    compact_input = self._compact_tool_output(tool_input)
                    text = f"Tool name: {tool_name};\nTool input: {compact_input}"
                    spending.input_tokens += self._get_tokens_count(text=text)

                    yield AgentMessage(
                        role="tool",
                        text=text,
                    )
                case "on_tool_end":
                    tool_name = event["name"]
                    logger.info("[%s] Tool call finished tool=%s", request_id, tool_name)
                    tool_output = event["data"].get("output")
                    compact_output = self._compact_tool_output(tool_output)
                    text = f"Tool name: {tool_name};\nTool output: {compact_output}"
                    spending.input_tokens += self._get_tokens_count(text=text)

                    yield AgentMessage(
                        role="tool",
                        text=text,
                    )
                case "on_tool_error":
                    tool_name = event["name"]
                    logger.error("[%s] Tool call error tool=%s", request_id, tool_name)
                    error_data = event["data"]
                    error_message = self._compact_tool_output(error_data.get("error", "Unknown error"))
                    text = f"Tool name: {tool_name};\nError: {error_message}"
                    spending.input_tokens += self._get_tokens_count(text=text)

                    yield AgentMessage(
                        role="tool",
                        text=text,
                    )

        logger.info("[%s] Agent ask finished", request_id)

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
            self._get_tokens_count(text=message.content)
            for message in summary_messages
        )
        spending.output_tokens = self._get_tokens_count(text=response.content)
        if self._model_settings.costs is not None:
            spending.calculate_cost(model_costs=self._model_settings.costs)
        
        return AgentMessage(
            role="system",
            text=response.content,
            is_summary=True,
            spending=spending,
        )

    async def summarize_dialogue(
            self, 
            messages: list[AgentMessage], 
            max_tokens: int = 300,
    ) -> AgentMessage:
        if not messages:
            return AgentMessage(
                role="system",
                text="Dialog is empty",
                is_summary=True,
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
            self._get_tokens_count(text=message.content)
            for message in summary_messages
        )
        spending.output_tokens = self._get_tokens_count(text=response.content)
        if self._model_settings.costs is not None:
            spending.calculate_cost(model_costs=self._model_settings.costs)
        
        return AgentMessage(
            role="system",
            text=(
                "Summary of the previous dialogue:\n"
                f"{response.content}"
            ),
            is_summary=True,
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
            if is_daily else
            "You are an expert at extracting long-term important information from dialogues."
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

        model_name = getattr(self._client, "model_name", None) or self._model_settings.id

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
        template_path = self.TEMPLATES_DIR / "agent_prompt.j2"
        template_content = template_path.read_text()
        template = Template(template_content)

        toolkits = dict(self._toolkits)
        tools = list(self._tools)
        if channel is not None:
            channel_toolkit = channel.get_toolkit()
            if channel_toolkit is not None:
                toolkits["channel"] = channel_toolkit
                tools.extend(channel_toolkit.get_tools())

        mcps = {}
        for server_name, mcp_setting in self._mcp_settings.items():
            mcps[server_name] = MCPInfo(
                name=server_name,
                description=mcp_setting.description,
            )

        memories = await self._get_memory_context()
        agent_prompt_values = AgentPromptValues(
            agent_identity=self._settings.identity,
            system=SystemValues(time=datetime.datetime.now(datetime.timezone.utc)),
            max_tool_calls=self._settings.max_tool_calls,
            toolkits=toolkits,
            tools=tools,
            channel=channel,
            memories=memories,
            mcps=mcps,
        )

        prompt = template.render(data=agent_prompt_values)
        return prompt

    async def _get_memory_context(self) -> dict[str, str]:
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
        template_path = (
            self.TEMPLATES_DIR / "summarize_memory_daily_prompt.j2"
            if is_daily else
            self.TEMPLATES_DIR / "summarize_memory_prompt.j2"
        )
        template_content = template_path.read_text()
        template = Template(template_content)

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
        template_path = self.TEMPLATES_DIR / "summarize_dialogue_prompt.j2"
        template_content = template_path.read_text()
        template = Template(template_content)

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
        template_path = (
            self.TEMPLATES_DIR / "extract_dialogue_info_daily_prompt.j2"
            if is_daily else
            self.TEMPLATES_DIR / "extract_dialogue_info_prompt.j2"
        )
        template_content = template_path.read_text()
        template = Template(template_content)

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
        half = max((max_len - len(separator)) // 2, 0)
        return text[:half] + separator + text[-half:]

    def _extract_subagent_spending(self, tool_output: Any) -> Spending | None:
        if not isinstance(tool_output, list):
            return None

        total_spending = None
        for message in tool_output:
            if not isinstance(message, dict):
                continue
            
            spending_data = message.get("spending")
            if not spending_data:
                continue
            
            try:
                message_spending = Spending(**spending_data)
                if total_spending is None:
                    total_spending = message_spending
                else:
                    total_spending += message_spending
            except (TypeError, ValueError):
                continue

        return total_spending

    def _convert_to_langchain_messages(self, messages: list[AgentMessage]) -> list[BaseMessage]:
        langchain_messages = []
        for agent_message in messages:
            if agent_message.text is None:
                continue
            langchain_message = None
            match agent_message.role:
                case "system":
                    langchain_message = SystemMessage(content=agent_message.text)
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
    except BaseException as exception:
        tb = "".join(
            traceback.format_exception(type(exception), exception, exception.__traceback__),
        )
        return ToolMessage(
            content=f"Tool error: {exception}\n\nTraceback:\n{tb}",
            tool_call_id=request.tool_call["id"],
        )
