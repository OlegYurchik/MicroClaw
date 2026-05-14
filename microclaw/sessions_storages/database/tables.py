import uuid
from datetime import datetime
from typing import Self

from sqlmodel import Column, Field, JSON, Relationship, Text

from microclaw.dto import AgentMessage, Spending
from microclaw.utils.database.tables import BaseTable
from .dto import SessionData


class SessionTable(BaseTable, table=True):
    __tablename__ = "sessions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    context_size: int = Field(default=0)
    spending: dict | None = Field(default=None, sa_column=Column(JSON))

    messages: list["MessageTable"] = Relationship(back_populates="session")

    @classmethod
    def from_item(cls, item: "SessionData") -> Self:
        return cls(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            context_size=item.context,
            spending=item.spending.model_dump() if item.spending else None,
        )

    def to_item(self) -> "SessionData":
        return SessionData(
            id=self.id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            context=self.context_size,
            spending=Spending(**self.spending) if self.spending else None,
        )


class MessageTable(BaseTable, table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="sessions.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    role: str = Field(sa_column=Column(Text))
    text: str | None = Field(default=None, sa_column=Column(Text))
    chunked_message_id: str | None = Field(default=None)
    spending: dict | None = Field(default=None, sa_column=Column(JSON))
    is_summary: bool = Field(default=False)
    audio: bytes | None = Field(default=None)
    audio_format: str | None = Field(default=None)

    session: SessionTable = Relationship(back_populates="messages")

    @classmethod
    def from_item(cls, item: AgentMessage, session_id: uuid.UUID) -> Self:
        return cls(
            session_id=session_id,
            role=item.role,
            text=item.text,
            chunked_message_id=item.chunked_message_id,
            spending=item.spending.model_dump() if item.spending else None,
            is_summary=item.is_summary,
            audio=item.audio,
            audio_format=item.audio_format,
        )

    def to_item(self) -> AgentMessage:
        return AgentMessage(
            role=self.role,
            text=self.text,
            chunked_message_id=self.chunked_message_id,
            spending=Spending(**self.spending) if self.spending else None,
            is_summary=self.is_summary,
            audio=self.audio,
            audio_format=self.audio_format,
        )
