import datetime
import pathlib
from typing import AsyncGenerator

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
from langchain.agents import create_agent

from microclaw.agents.settings import (
    AgentSettings,
    ModelSettings,
    ProviderSettings,
    APITypeEnum,
    MCPSettings,
)
from microclaw.dto import AgentMessage, Spending
from microclaw.toolkits import BaseToolKit
from .dto import SystemPromptValues, SystemValues


class Agent:
    def __init__(
            self,
            settings: AgentSettings,
            model_settings: ModelSettings,
            provider_settings: ProviderSettings,
            toolkits: dict[str, BaseToolKit],
            mcp: MultiServerMCPClient,
    ):
        self._settings = settings
        self._model_settings = model_settings
        self._provider_settings = provider_settings
        self._toolkits = toolkits
        self._mcp = mcp
        self._tools = [
            tool
            for toolkit in self._toolkits.values()
            for tool in toolkit.get_tools()
        ]
        self._client = self.get_client()

    def get_client(self):
        api_type = self._model_settings.api_type or self._provider_settings.api_type
        api_key = self._model_settings.api_key or self._provider_settings.api_key
        if not api_key:
            raise ValueError("API key for agent not provided")
        base_url = str(self._provider_settings.base_url)
        default_headers = self._provider_settings.headers | self._model_settings.headers
        temperature = self._settings.temperature or self._model_settings.temperature or 1

        match api_type:
            case APITypeEnum.OPENAI:
                return ChatOpenAI(
                    model=self._model_settings.id,
                    api_key=api_key,
                    base_url=base_url if base_url != "https://api.openai.com/v1" else None,
                    default_headers=default_headers,
                    temperature=temperature,
                )
            case APITypeEnum.CLOUDRU:
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
            case _:
                raise ValueError(f"Unsupported API type: '{api_type.value}'")

    async def ask(
            self,
            messages: list[AgentMessage],
            channel: "ChannelInterface" = None,
    ) -> AsyncGenerator[AgentMessage]:
        langchain_messages: list[BaseMessage] = self._convert_to_langchain_messages(messages)

        tools = list(self._tools) + list(await self._mcp.get_tools())
        channel_toolkit = channel.get_toolkit()
        if channel_toolkit is not None:
            tools.extend(channel_toolkit.get_tools())

        config = {
            "recursion_limit": self._settings.max_tool_calls,
        }
        
        agent = create_agent(
            model=self._client,
            tools=tools,
            system_prompt=await self._get_system_prompt(channel=channel),
        )
        
        events_generator = agent.astream_events(
            {"messages": langchain_messages},
            config=config,
            version="v2",
        )

        spending = self._get_empty_spending()
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
                    yield AgentMessage(
                        role="assistant",
                        text=text,
                        chunked_message_id=chunk.id,
                    )
                case "on_chat_model_end":
                    output = event["data"]["output"]
                    text = self._convert_content_to_text(output.content)
                    if text is not None:
                        spending.output_tokens = self._get_tokens_count(text=output.content)
                    if self._model_settings.costs is not None:
                        spending.calculate_cost(model_costs=self._model_settings.costs)
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
                    yield AgentMessage(
                        role="tool",
                        text=f"Tool name: {event["name"]}; tool output: {event["data"].get("output")}",
                        chunked_message_id=event["run_id"],
                        spending=None,
                    )

    async def summarize_dialog(
            self, 
            messages: list[AgentMessage], 
            max_summary_tokens: int = 200,
    ) -> AgentMessage:
        dialog_text = "\n".join(
            f"{message.role}: {message.text}"
            for message in messages
        )

        if not dialog_text.strip():
            return AgentMessage(
                role="system",
                text="Dialog is empty",
                is_summary=True,
            )
        
        summary_prompt = f"""
        Summarize the following dialogue. 
        Preserve all key information, including facts, questions, and answers.
        The summary must be concise (maximum {max_summary_tokens} tokens) 
        and written in the SAME LANGUAGE as the dialogue itself.

        Dialogue:
        {dialog_text}

        Summary:
        """
        
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

    def get_model_context_window_size(self) -> int | None:
        if self._model_settings.context_window_size is not None:
            return self._model_settings.context_window_size

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

    async def _get_system_prompt(self, channel: "ChannelInterface") -> str:
        template_path = (
            pathlib.Path(__file__).parent / "templates" / "system_prompt.j2"
        )
        template_content = template_path.read_text()
        template = Template(template_content)

        toolkits = list(self._toolkits)
        tools = list(self._tools) + list(await self._mcp.get_tools())
        channel_toolkit = channel.get_toolkit()
        if channel_toolkit is not None:
            toolkits.append(channel_toolkit)
            tools.extend(channel_toolkit.get_tools())

        system_prompt_values = SystemPromptValues(
            agent_identity=self._settings.identity,
            system=SystemValues(time=datetime.datetime.now(datetime.timezone.utc)),
            toolkits=toolkits,
            tools=tools,
            channel=channel,
        )

        prompt = template.render(data=system_prompt_values)
        return prompt

    def _get_empty_spending(self) -> Spending:
        return Spending(
            currency=(
                self._model_settings.costs.currency
                if self._model_settings.costs is not None
                else "$"
            ),
        )

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
