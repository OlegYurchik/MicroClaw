from microclaw.dto import AgentMessage
from microclaw.toolkits import BaseToolKit, ToolKitSettings, tool
from .settings import SubAgentSettings


class SubAgentToolKit(BaseToolKit):
    def __init__(self, settings: SubAgentSettings, agent: "Agent"):
        self._name = settings.name
        self._agent = agent
        self._max_turns = settings.max_turns
        self._summarize_threshold_tokens = settings.summarize_threshold_tokens

        toolkit_settings = ToolKitSettings(
            path="",
            prompt=settings.description,
        )
        super().__init__(key=settings.name, settings=toolkit_settings)

    @property
    def name(self) -> str:
        return self._name

    @tool
    async def call_agent(self, query: str) -> list[dict]:
        """Call the subagent with a query and return all messages from the conversation.

        Args:
            query: The message/question to send to the subagent

        Returns:
            List of messages from the subagent conversation, including assistant responses
            and tool calls. Each message is a dict with role, text, and optional spending.
        """
        messages = [AgentMessage(role="user", text=query)]

        result_messages = []
        total_tokens = 0
        turn = 0

        async for message in self._agent.ask(messages=messages, stream=False):
            if self._max_turns is not None and turn > self._max_turns:
                raise Exception(f"Subagent exceeded maximum number of turns ({self._max_turns})")

            if message.role == "assistant":
                message.role = "subagent"
            result_messages.append(message)
            if message.spending:
                total_tokens = message.spending.get_total_tokens()
            turn += 1

        if (
                self._summarize_threshold_tokens is not None and
                total_tokens >= self._summarize_threshold_tokens
        ):
            summary = await self._agent.summarize_dialogue(
                messages=result_messages,
            )
            result_messages = [summary]
        return result_messages
