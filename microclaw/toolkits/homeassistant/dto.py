from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Context(BaseModel):
    """Model for entity state contexts from Home Assistant."""

    id: str = Field(description="Unique string identifying the context")
    parent_id: str | None = Field(
        default=None,
        description="Unique string identifying the parent context",
    )
    user_id: str | None = Field(
        default=None,
        description="Unique string identifying the user",
    )


class State(BaseModel):
    """Represents the state of an entity."""

    entity_id: str = Field(description="Entity identifier")
    state: str = Field(description="Current state value")
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Entity attributes",
    )
    last_changed: datetime | None = Field(
        default=None,
        description="Last time the state changed",
    )
    last_updated: datetime | None = Field(
        default=None,
        description="Last time the entity was updated",
    )
    last_reported: datetime | None = Field(
        default=None,
        description="Last time the state was reported to the server",
    )
    context: Context | None = Field(
        default=None,
        description="Context information",
    )


class Entity(BaseModel):
    """Represents a Home Assistant entity."""

    entity_id: str = Field(description="Entity identifier (e.g., light.living_room)")
    slug: str = Field(description="Entity slug (e.g., living_room)")
    domain: str = Field(description="Domain of the entity (e.g., light, switch, sensor)")
    state: State | None = Field(default=None, description="Current state of the entity")


class Service(BaseModel):
    """Represents a Home Assistant service."""

    domain: str = Field(description="Domain of the service (e.g., light, switch)")
    service_id: str = Field(description="Service identifier (e.g., turn_on, turn_off)")
    name: str | None = Field(default=None, description="Service name")
    description: str | None = Field(default=None, description="Service description")
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Service fields/parameters",
    )
    target: dict[str, Any] | None = Field(
        default=None,
        description="Service target selector",
    )
    response: dict[str, Any] | None = Field(
        default=None,
        description="Service response schema",
    )
