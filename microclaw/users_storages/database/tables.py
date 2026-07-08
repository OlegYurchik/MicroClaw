import uuid
from typing import Self

from pydantic import AwareDatetime
from sqlmodel import Column, DateTime, Field, Index, JSON, Relationship, Text

from microclaw.dto import UserRoleEnum
from microclaw.utils.database.tables import BaseTable
from .dto import CronData, SessionData, UserData


class UserTable(BaseTable, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    role: UserRoleEnum = Field(default=UserRoleEnum.USER, sa_column=Column(Text))
    agent: dict | None = Field(default=None, sa_column=Column(JSON))

    sessions: list["SessionTable"] = Relationship(back_populates="user")
    tokens: list["TokenTable"] = Relationship(back_populates="user")

    @classmethod
    def from_item(cls, item: UserData) -> Self:
        return cls(
            id=item.id,
            role=item.role,
            agent=item.agent,
        )

    def to_item(self) -> UserData:
        return UserData(
            id=self.id,
            role=self.role,
            agent=self.agent,
        )


class SessionTable(BaseTable, table=True):
    __tablename__ = "user_sessions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    channel_key: str = Field(sa_column=Column(Text))
    channel_internal_id: str = Field(sa_column=Column(Text))

    user: UserTable = Relationship(back_populates="sessions")

    __table_args__ = (
        Index("ix_user_sessions_id", "id"),
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_channel", "channel_key", "channel_internal_id"),
    )

    @classmethod
    def from_item(cls, item: SessionData) -> Self:
        return cls(
            id=item.id,
            user_id=item.user_id,
            channel_key=item.channel_key,
            channel_internal_id=item.channel_internal_id,
        )

    def to_item(self) -> SessionData:
        return SessionData(
            id=self.id,
            user_id=self.user_id,
            channel_key=self.channel_key,
            channel_internal_id=self.channel_internal_id,
        )


class CronTable(BaseTable, table=True):
    __tablename__ = "user_crons"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    path: str = Field(sa_column=Column(Text))
    cron: str = Field(sa_column=Column(Text))
    enabled: bool = True
    args: dict | None = Field(default=None, sa_column=Column(JSON))

    __table_args__ = (
        Index("ix_user_crons_id", "id"),
        Index("ix_user_crons_user_id", "user_id"),
    )

    @classmethod
    def from_item(cls, item: CronData) -> Self:
        return cls(
            id=item.id,
            user_id=item.user_id,
            path=item.path,
            cron=item.cron,
            enabled=item.enabled,
            args=item.args,
        )

    def to_item(self) -> CronData:
        return CronData(
            id=self.id,
            user_id=self.user_id,
            path=self.path,
            cron=self.cron,
            enabled=self.enabled,
            args=self.args,
        )


class TokenTable(BaseTable, table=True):
    __tablename__ = "user_tokens"

    token: str = Field(sa_column=Column(Text, primary_key=True))
    user_id: uuid.UUID = Field(foreign_key="users.id")
    expires_at: AwareDatetime | None = Field(default=None, sa_column=Column(DateTime))

    user: UserTable = Relationship(back_populates="tokens")

    __table_args__ = (Index("ix_user_tokens_user_id", "user_id"),)
