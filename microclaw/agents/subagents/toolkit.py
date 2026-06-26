from microclaw.dto import AgentMessage
from microclaw.toolkits import BaseToolKit, ToolKitSettings, tool
from .settings import SubAgentSettings


class SubAgentToolKit(BaseToolKit):
    def __init__(
            self,
            settings: SubAgentSettings,
            agent: "Agent",  # noqa: F821
    ):
        self._name = settings.name
        self._agent = agent
        self._max_turns = settings.max_turns

        toolkit_settings = ToolKitSettings(
            path="",
            prompt=settings.description,
        )
        super().__init__(key=settings.name, settings=toolkit_settings)

    @property
    def name(self) -> str:
        return self._name

    @tool
    async def call_agent(self, query: str) -> AgentMessage | None:
        """Call the subagent with a query and return only the result.

        Args:
            query: The message/question to send to the subagent

        Returns:
            The final response message
        """
        query_message = AgentMessage(role="user", text=query)
        last_message = None
        total_spending = None
        turn = 0

        async for message in self._agent.ask(messages=[query_message], stream=False):
            if message.text is not None:
                last_message = message

            if self._max_turns is not None and turn > self._max_turns:
                raise Exception(f"Subagent exceeded maximum number of turns ({self._max_turns})")

            if message.spending:
                if total_spending is None:
                    total_spending = message.spending
                else:
                    total_spending += message.spending
            turn += 1

        if last_message is not None and total_spending is not None:
            last_message.spending = total_spending
        return last_message
