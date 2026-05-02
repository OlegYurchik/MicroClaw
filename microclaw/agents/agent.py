import datetime
import pathlib
from typing import Any, AsyncGenerator

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
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

from microclaw.agents.settings import (
    AgentSettings,
    ModelSettings,
    ProviderSettings,
    APITypeEnum,
    MCPSettings,
)
from microclaw.dto import AgentMessage, Spending
from microclaw.toolkits import BaseToolKit
from microclaw.toolkits.memory import MemoryToolKit
from .dto import SummaryValues, SummaryMemoryValues, SystemPromptValues, SystemValues
from .subagents import SubAgentToolKit


class Agent:
    TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"

    def __init__(
            self,
            settings: AgentSettings,
            model_settings: ModelSettings,
            provider_settings: ProviderSettings,
            toolkits: dict[str, BaseToolKit],
            mcp: MultiServerMCPClient,
            subagents_toolkits: list[SubAgentToolKit] | None = None,
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

        self._mcp = mcp
        self._subagents_toolkits = subagents_toolkits.copy() if subagents_toolkits else []
        self._tools = [
            tool
            for toolkit in self._toolkits.values()
            for tool in toolkit.get_tools()
        ]
        self._client = self.get_client()

    def set_subagents_toolkits(self, subagents_toolkits: list[SubAgentToolKit]):
        self._subagents_toolkits = subagents_toolkits.copy()

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
            channel: "BaseChannel | None" = None,
            stream: bool = False,
    ) -> AsyncGenerator[AgentMessage]:
        langchain_messages: list[BaseMessage] = self._convert_to_langchain_messages(messages)

        tools = list(self._tools) + list(await self._mcp.get_tools())
        if channel is not None:
            channel_toolkit = channel.get_toolkit()
            if channel_toolkit is not None:
                tools.extend(channel_toolkit.get_tools())
        for subagent_toolkit in self._subagents_toolkits:
            tools.extend(subagent_toolkit.get_tools())

        config = {
            "recursion_limit": self._settings.max_tool_calls,
        }
        
        agent = create_agent(
            model=self._client,
            tools=tools,
            system_prompt=await self._get_agent_prompt(channel=channel),
            middleware=[_handle_tool_errors],
        )

        events_generator = agent.astream_events(
            {"messages": langchain_messages},
            config=config,
            version="v2",
        )

        spending = self._get_empty_spending()
        accumulated_messages: dict[str, str] = {}
 
        async for event in events_generator:
            event_type = event["event"]
            match event_type:
                case "on_chat_model_start":
                    spending.input_tokens += sum(
                        self._get_tokens_count(
                            text=self._convert_content_to_text(message.content) or "",
                        )
                        for messages_list in event["data"]["input"]["messages"]
                        for message in messages_list
                    )
                case "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    text = self._convert_content_to_text(chunk.content)
                    if text is None:
                        continue
                    message = AgentMessage(
                        role="assistant",
                        text=text,
                        chunked_message_id=chunk.id,
                    )
                    if stream:
                        yield message
                    else:
                        if chunk.id not in accumulated_messages:
                            accumulated_messages[chunk.id] = message
                        accumulated_messages[chunk.id].text += text
                case "on_chat_model_end":
                    output = event["data"]["output"]
                    text = self._convert_content_to_text(output.content)
                    if text is not None:
                        spending.output_tokens = self._get_tokens_count(text=output.content)
                    if self._model_settings.costs is not None:
                        spending.calculate_cost(model_costs=self._model_settings.costs)
                    if not stream and accumulated_messages:
                        for accumulated_message in accumulated_messages.values():
                            yield accumulated_message
                        accumulated_messages.clear()
                    
                    yield AgentMessage(
                        role="assistant",
                        spending=spending,
                    )
                    spending = self._get_empty_spending()
                case "on_tool_start":
                    yield AgentMessage(
                        role="tool",
                        text=f"Tool name: {event["name"]}; tool input: {event["data"].get("input", {})}",
                        chunked_message_id=event["run_id"],
                        spending=None,
                    )
                case "on_tool_end":
                    tool_output = event["data"].get("output")
                    subagent_spending = self._extract_subagent_spending(tool_output)
                    yield AgentMessage(
                        role="tool",
                        text=f"Tool name: {event["name"]}; tool output: {tool_output}",
                        chunked_message_id=event["run_id"],
                        spending=subagent_spending,
                    )
                case "on_tool_error":
                    error_data = event["data"]
                    error_message = error_data.get("error", "Unknown error")
                    tool_name = event["name"]
                    yield AgentMessage(
                        role="tool",
                        text=f"Tool name: {tool_name}; error: {error_message}",
                        chunked_message_id=event["run_id"],
                        spending=None,
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
            new_content=new_context,
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

    async def _get_agent_prompt(self, channel: "BaseChannel | None") -> str:
        template_path = self.TEMPLATES_DIR / "agent_prompt.j2"
        template_content = template_path.read_text()
        template = Template(template_content)

        toolkits = dict(self._toolkits)
        tools = list(self._tools) + list(await self._mcp.get_tools())
        if channel is not None:
            channel_toolkit = channel.get_toolkit()
            if channel_toolkit is not None:
                toolkits["channel"] = channel_toolkit
                tools.extend(channel_toolkit.get_tools())

        memories = await self._get_memory_context()
        system_prompt_values = SystemPromptValues(
            agent_identity=self._settings.identity,
            system=SystemValues(time=datetime.datetime.now(datetime.timezone.utc)),
            toolkits=toolkits,
            tools=tools,
            channel=channel,
            memories=memories,
            subagents=self._subagents_toolkits,
        )

        prompt = template.render(data=system_prompt_values)
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
        return ToolMessage(
            content=f"Tool error: {exception}",
            tool_call_id=request.tool_call["id"],
        )
