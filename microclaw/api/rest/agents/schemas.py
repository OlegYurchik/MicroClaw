from typing import Any, Self

from pydantic import BaseModel

from microclaw.api.rest.schemas import ListResponse


class AgentIdentityResponse(BaseModel):
    name: str = "MicroClaw"
    emoji: str = "🤖"
    creature: str = "*(AI? robot? familiar? ghost in the machine? something weirder?)*"
    vibe: str = "*(how do you come across? sharp? warm? chaotic? calm?)*"
    description: str | None = None


class AgentResponse(BaseModel):
    id: str
    identity: AgentIdentityResponse
    model: str | None

    @classmethod
    def from_item(cls, item: tuple[str, Any]) -> Self:
        name, settings = item
        return cls(
            id=name,
            identity=AgentIdentityResponse(
                name=settings.identity.name,
                emoji=settings.identity.emoji,
                creature=settings.identity.creature,
                vibe=settings.identity.vibe,
                description=settings.identity.description,
            ),
            model=(
                settings.model.id
                if hasattr(settings.model, "id")
                else settings.model
            ),
        )


class AgentListResponse(ListResponse[AgentResponse]):

    @classmethod
    def from_items(cls, items: list[tuple[str, Any]]) -> Self:
        return cls(
            data=[AgentResponse.from_item(item=item) for item in items],
            total=len(items),
        )
