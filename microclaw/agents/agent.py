import datetime
import pathlib
from typing import AsyncGenerator

from jinja2 import Template
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from microclaw.agents.settings import AgentSettings, ModelSettings, ProviderSettings, APITypeEnum
from microclaw.dto import AgentMessage, Spending
from microclaw.toolkits import BaseToolKit
from .dto import SystemPromptValues, SystemValues


class Agent:
    def __init__(
            self,
            settings: AgentSettings,
            model_settings: ModelSettings,
            provider_settings: ProviderSettings,
            toolkits: list[BaseToolKit],
            tools: list[LangChainBaseTool],
    ):
        self._settings = settings
        self._model_settings = model_settings
        self._provider_settings = provider_settings
        self._toolkits = toolkits
        self._tools = tools
        self._agent = self.get_agent()

    def get_agent(self):
        api_type = self._model_settings.api_type or self._provider_settings.api_type
        api_key = self._model_settings.api_key or self._provider_settings.api_key
        if not api_key:
            raise ValueError("API key for agent not provided")
        base_url = str(self._provider_settings.base_url)
        default_headers = self._provider_settings.headers | self._model_settings.headers
        temperature = self._settings.temperature or self._model_settings.temperature or 1

        match api_type:
            case APITypeEnum.OPENAI:
                self._client = ChatOpenAI(
                    model=self._model_settings.id,
                    api_key=api_key,
                    base_url=base_url if base_url != "https://api.openai.com/v1" else None,
                    default_headers=default_headers,
                    temperature=temperature,
                )
            case _:
                raise ValueError(f"Unsupported API type: '{api_type.value}'")

        return create_agent(
            model=self._client,
            tools=self._tools,
            system_prompt=self.get_system_prompt(),
        )

    async def ask(
            self,
            messages: list[AgentMessage],
    ) -> AsyncGenerator[AgentMessage]:
        langchain_messages: list[BaseMessage] = self._convert_to_langchain_messages(messages)

        config = {
            "recursion_limit": self._settings.max_tool_calls,
        }
        events_generator = self._agent.astream_events(
            {"messages": langchain_messages},
            config=config,
            version="v2",
        )
        
        async for event in events_generator:
            event_type = event["event"]
            spending = Spending(
                input_tokens=0,
                output_tokens=0,
                cache_read_tokens=0,
                cache_write_tokens=0,
                cost=0,
            )
            if self._model_settings.costs is not None:
                spending.calculate_cost(model_costs=self._model_settings.costs)

            if event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if not chunk.content:
                    continue
                yield AgentMessage(
                    role="assistant",
                    content=chunk.content,
                    chunked_message_id=chunk.id,
                    spending=spending,
                )
            elif event_type == "on_chat_model_end":
                output = event["data"]["output"]
                if hasattr(output, "usage_metadata") and output.usage_metadata:
                    usage = output.usage_metadata
                    spending.input_tokens = usage.get("input_tokens", 0)
                    spending.output_tokens = usage.get("output_tokens", 0)
                    spending.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
                    spending.cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
                    if self._model_settings.costs is not None:
                        spending.calculate_cost(model_costs=self._model_settings.costs)
                yield AgentMessage(
                    role="assistant",
                    content="",
                    spending=spending,
                )
            elif event_type == "on_tool_start":
                yield AgentMessage(
                    role="tool",
                    content=f"Tool name: {event["name"]}; tool input: {event["data"].get("input", {})}",
                    chunked_message_id=event["run_id"],
                    spending=spending,
                )
            elif event_type == "on_tool_end":
                yield AgentMessage(
                    role="tool",
                    content=f"Tool name: {event["name"]}; tool input: {event["data"].get("output")}",
                    chunked_message_id=event["run_id"],
                    spending=spending,
                )
            else:
                yield AgentMessage(
                    role=event_type,
                    content="",
                    spending=spending,
                )

    async def summarize_dialog(
            self, 
            messages: list[AgentMessage], 
            max_summary_tokens: int = 200,
            language: str = "ru",
    ) -> AgentMessage:
        dialog_text = "\n".join(
            f"{message.role}: {message.content}"
            for message in messages
            if message.role in ("user", "assistant", "system")
        )

        if not dialog_text.strip():
            return AgentMessage(
                role="system",
                content="Диалог пуст.",
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
        
        return AgentMessage(
            role="system",
            content=(
                "Summary of the previous dialogue:\n"
                f"{response.content}"
            ),
            is_summary=True,
        )

    def get_system_prompt(self) -> str:
        template_path = (
            pathlib.Path(__file__).parent / "templates" / "system_prompt.j2"
        )
        template_content = template_path.read_text()
        template = Template(template_content)

        system_prompt_values = SystemPromptValues(
            agent_identity=self._settings.identity,
            system=SystemValues(time=datetime.datetime.now(datetime.timezone.utc)),
            toolkits=self._toolkits,
            tools=self._tools,
        )

        prompt = template.render(data=system_prompt_values)
        return prompt

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

    def _convert_to_langchain_messages(self, messages: list[AgentMessage]) -> list[BaseMessage]:
        langchain_messages = []
        for agent_message in messages:
            langchain_message = None
            match agent_message.role:
                case "system":
                    langchain_message = SystemMessage(content=agent_message.content)
                case "user":
                    langchain_message = HumanMessage(content=agent_message.content)
                case "assistant":
                    langchain_message = AIMessage(content=agent_message.content)
                case _:
                    langchain_message = HumanMessage(content=agent_message.content)
            langchain_messages.append(langchain_message)
        return langchain_messages
