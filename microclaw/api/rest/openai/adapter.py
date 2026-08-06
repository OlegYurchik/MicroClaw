from typing import Any

from microclaw.dto import AgentMessage


class OpenAIMessageAdapter:
    _OPENAI_ROLE_TO_AGENT_ROLE = {
        "system": "system",
        "user": "user",
        "assistant": "assistant",
        "tool": "tool",
    }

    @classmethod
    def to_agent_message(cls, message: dict[str, Any]) -> AgentMessage:
        role = message.get("role", "user")
        content = message.get("content")

        if isinstance(content, list):
            content = next(
                (
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ),
                "",
            )

        agent_role = cls._OPENAI_ROLE_TO_AGENT_ROLE.get(role, "user")

        return AgentMessage(
            role=agent_role,
            text=content if content is not None else "",
        )
