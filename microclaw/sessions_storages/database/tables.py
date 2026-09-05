import datetime
import json
from typing import Self
import uuid

from .dto import SessionData
from metaorm import BaseTable, Field

from microclaw.dto import AgentMessage, Spending
from microclaw.utils import utcnow


class SessionTable(BaseTable, table=True):
    __tablename__ = "sessions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime.datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime.datetime = Field(default_factory=utcnow, index=True)
    channel_key: str = Field(index=True)
    channel_internal_id: str
    context_size: int = Field(default=0)
    spending: str | None = Field(default=None)

    @staticmethod
    def serialize_spending(spending: Spending | None) -> str | None:
        return json.dumps(spending.model_dump()) if spending is not None else None

    @classmethod
    def from_item(cls, item: SessionData) -> Self:
        return cls(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            channel_key=item.channel_key,
            channel_internal_id=item.channel_internal_id,
            context_size=item.context_size,
            spending=cls.serialize_spending(item.spending),
        )

    def to_item(self) -> SessionData:
        return SessionData(
            id=self.id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            channel_key=self.channel_key,
            channel_internal_id=self.channel_internal_id,
            context_size=self.context_size,
            spending=Spending.model_validate_json(self.spending) if self.spending is not None else None,
        )


class MessageTable(BaseTable[AgentMessage], table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="sessions.id", index=True)
    created_at: datetime.datetime = Field(default_factory=utcnow)
    role: str
    text: str | None = Field(default=None)
    chunked_message_id: str | None = Field(default=None)
    spending: str | None = Field(default=None)
    audio: bytes | None = Field(default=None)
    audio_format: str | None = Field(default=None)

    @classmethod
    def from_item(cls, item: AgentMessage, session_id: uuid.UUID) -> Self:
        return cls(
            id=item.id or uuid.uuid4(),
            session_id=session_id,
            role=item.role,
            text=item.text,
            chunked_message_id=item.chunked_message_id,
            spending=json.dumps(item.spending.model_dump()) if item.spending is not None else None,
            audio=item.audio,
            audio_format=item.audio_format,
        )

    def to_item(self) -> AgentMessage:
        return AgentMessage(
            id=self.id,
            role=self.role,
            text=self.text,
            chunked_message_id=self.chunked_message_id,
            spending=Spending.model_validate_json(self.spending) if self.spending is not None else None,
            audio=self.audio,
            audio_format=self.audio_format,
        )
