import datetime
from typing import Self
import uuid

from metaorm import BaseTable, Field
from sqlalchemy import JSON, Column, UniqueConstraint

from microclaw.dto import CronTask, Token, User, UserChannel, UserRoleEnum, Webhook


class UserTable(BaseTable[User], table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    role: UserRoleEnum = Field(default=UserRoleEnum.USER)
    agent: dict | None = Field(default=None, sa_column=Column(JSON))

    @classmethod
    def from_item(cls, item: User) -> Self:
        return cls(
            id=item.id,
            role=item.role,
            agent=item.agent,
        )

    def to_item(self) -> User:
        return User(
            id=self.id,
            role=self.role,
            agent=self.agent,
        )


class UserChannelTable(BaseTable[UserChannel], table=True):
    __tablename__ = "user_channels"

    __table_args__ = (UniqueConstraint("channel_key", "channel_internal_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    channel_key: str = Field(index=True)
    channel_internal_id: str = Field(index=True)
    actual_session_id: uuid.UUID | None = None

    @classmethod
    def from_item(cls, item: UserChannel) -> Self:
        return cls(
            user_id=item.user_id,
            channel_key=item.channel_key,
            channel_internal_id=item.channel_internal_id,
            actual_session_id=item.actual_session_id,
        )

    def to_item(self) -> UserChannel:
        return UserChannel(
            user_id=self.user_id,
            channel_key=self.channel_key,
            channel_internal_id=self.channel_internal_id,
            actual_session_id=self.actual_session_id,
        )


class CronTable(BaseTable[CronTask], table=True):
    __tablename__ = "user_crons"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    path: str
    cron: str
    enabled: bool = True
    args: dict | None = Field(default=None, sa_column=Column(JSON))

    @classmethod
    def from_item(cls, item: CronTask) -> Self:
        return cls(
            id=item.id,
            user_id=item.user_id,
            path=item.path,
            cron=item.cron,
            enabled=item.enabled,
            args=item.args,
        )

    def to_item(self) -> CronTask:
        return CronTask(
            id=self.id,
            user_id=self.user_id,
            path=self.path,
            cron=self.cron,
            enabled=self.enabled,
            args=self.args if self.args is not None else {},
        )


class TokenTable(BaseTable[Token], table=True):
    __tablename__ = "user_tokens"

    token: str = Field(primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    expires_at: datetime.datetime | None = Field(default=None)

    @classmethod
    def from_item(cls, item: Token) -> Self:
        expires_at = item.expires_at
        if expires_at is not None and expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(datetime.timezone.utc)
        return cls(
            token=item.token,
            user_id=item.user_id,
            expires_at=expires_at,
        )

    def to_item(self) -> Token:
        expires_at = self.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        return Token(
            token=self.token,
            user_id=self.user_id,
            expires_at=expires_at,
        )


class WebhookTable(BaseTable[Webhook], table=True):
    __tablename__ = "user_webhooks"

    id: uuid.UUID = Field(primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    path: str
    enabled: bool = True
    args: dict | None = Field(default=None, sa_column=Column(JSON))
    agent: str | None = Field(default=None)
    channel: str | None = Field(default=None)
    channel_internal_id: str | None = Field(default=None)

    @classmethod
    def from_item(cls, item: Webhook) -> Self:
        return cls(
            id=item.id,
            user_id=item.user_id,
            path=item.path,
            enabled=item.enabled,
            args=item.args,
            agent=item.agent,
            channel=item.channel,
            channel_internal_id=item.channel_internal_id,
        )

    def to_item(self) -> Webhook:
        return Webhook(
            id=self.id,
            user_id=self.user_id,
            path=self.path,
            enabled=self.enabled,
            args=self.args if self.args is not None else {},
            agent=self.agent,
            channel=self.channel,
            channel_internal_id=self.channel_internal_id,
        )
