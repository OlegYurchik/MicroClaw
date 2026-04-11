from a2a.client import A2AClient
from a2a.types import Message, TextPart, Role, Task, TaskState

from microclaw.dto import AgentMessage, Spending
from microclaw.toolkits.base import BaseToolKit, tool
from .settings import A2AToolKitSettings


class A2AToolKit(BaseToolKit[A2AToolKitSettings]):
    """Toolkit for calling remote agents via A2A protocol."""

    def __init__(self, key: str, settings: A2AToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._client = A2AClient(str(self._settings.url))

    @tool
    async def call_agent(self, query: str) -> list[AgentMessage]:
        """
        Call a remote agent with a query and return all messages from the conversation.

        Args:
            query: The message/question to send to the remote agent

        Returns:
            List of AgentMessage objects from the remote agent conversation.

        Raises:
            RuntimeError: If the remote agent call fails
        """
        message = Message(
            role=Role.USER,
            parts=[TextPart(text=query)]
        )
        task = await self._client.create_task(message=message)

        while task.state not in (TaskState.COMPLETED, TaskState.FAILED):
            task = await self._client.get_task(task.id)

        if task.state == TaskState.FAILED:
            raise RuntimeError(f"Remote agent failed: {task.error}")

        return self._parse_result(task.result)

    def _parse_result(self, result) -> list[AgentMessage]:
        if result is None:
            return []
        if hasattr(result, "messages"):
            return [self._a2a_message_to_agent_message(msg) for msg in result.messages]
        if hasattr(result, "text"):
            return [AgentMessage(role="assistant", text=result.text)]
        if isinstance(result, list):
            return [self._a2a_message_to_agent_message(msg) for msg in result]
        return []

    def _a2a_message_to_agent_message(self, message) -> AgentMessage:
        text_parts = []
        if hasattr(message, "parts"):
            for part in message.parts:
                if hasattr(part, "text"):
                    text_parts.append(part.text)
        text = "\n".join(text_parts) if text_parts else None
        role = message.role.value if hasattr(message.role, "value") else str(message.role)

        spending = None
        if hasattr(message, "metadata") and message.metadata:
            if "spending" in message.metadata:
                spending = Spending(**message.metadata["spending"])

        return AgentMessage(role=role, text=text, spending=spending)
