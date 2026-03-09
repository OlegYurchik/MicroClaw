from datetime import datetime, date

from pydantic import BaseModel, Field


class Calendar(BaseModel):
    url: str = Field(description="URL of the calendar")
    name: str = Field(description="Display name of the calendar")


class Event(BaseModel):
    uid: str = Field(description="Unique identifier of the event")
    url: str | None = Field(default=None, description="URL link to the event")
    summary: str = Field(description="Title/summary of the event")
    description: str | None = Field(default=None, description="Description of the event")
    location: str | None = Field(default=None, description="Location of the event")
    start: datetime | date = Field(description="Start time of the event")
    end: datetime | date | None = Field(default=None, description="End time of the event")
    all_day: bool = Field(default=False, description="Whether the event is an all-day event")
