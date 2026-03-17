from datetime import datetime, date
from typing import Literal

from pydantic import BaseModel, Field


class TaskList(BaseModel):
    """Represents a task list (calendar) in Nextcloud Tasks."""

    url: str = Field(description="URL of the task list")
    name: str = Field(description="Display name of the task list")


class TaskPriority(BaseModel):
    """Task priority levels."""

    level: int = Field(
        ge=0,
        le=9,
        description="Priority level (0=undefined, 1=highest, 9=lowest)",
    )


class TaskStatus(BaseModel):
    """Task status."""

    value: Literal["NEEDS-ACTION", "IN-PROCESS", "COMPLETED", "CANCELLED"] = Field(
        description="Status of the task",
    )


class Task(BaseModel):
    """Represents a task in Nextcloud Tasks."""

    uid: str = Field(description="Unique identifier of the task")
    url: str | None = Field(default=None, description="URL link to the task")
    summary: str = Field(description="Title/summary of the task")
    description: str | None = Field(default=None, description="Description of the task")
    status: str | None = Field(default=None, description="Status of the task")
    priority: int | None = Field(
        default=None,
        ge=0,
        le=9,
        description="Priority level (0=undefined, 1=highest, 9=lowest)",
    )
    due: datetime | date | None = Field(default=None, description="Due date/time of the task")
    start: datetime | date | None = Field(default=None, description="Start date/time of the task")
    completed: bool = Field(default=False, description="Whether the task is completed")
    completed_at: datetime | None = Field(default=None, description="When the task was completed")
    created: datetime | None = Field(default=None, description="When the task was created")
    modified: datetime | None = Field(default=None, description="When the task was last modified")
    percent_complete: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage of task completion (0-100)",
    )
    categories: list[str] = Field(default_factory=list, description="Categories/tags for the task")
