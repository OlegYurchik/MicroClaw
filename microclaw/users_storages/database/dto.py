import uuid
from typing import Self

from pydantic import AwareDatetime, BaseModel

from microclaw.dto import CronTask, User, UserRoleEnum


class UserData(BaseModel):
    id: uuid.UUID
    role: UserRoleEnum = UserRoleEnum.USER
    agent: dict | None = None

    @classmethod
    def from_user(cls, user: User) -> Self:
        return cls(id=user.id, role=user.role, agent=user.agent)

    def to_user(self) -> User:
        return User(id=self.id, role=self.role, agent=self.agent)


class SessionData(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_key: str
    channel_internal_id: str


class CronData(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    path: str
    cron: str
    enabled: bool = True
    args: dict | None = None

    @classmethod
    def from_cron_task(cls, cron_task: CronTask, user_id: uuid.UUID) -> Self:
        return cls(
            id=cron_task.id,
            user_id=user_id,
            path=cron_task.path,
            cron=cron_task.cron,
            enabled=cron_task.enabled,
            args=cron_task.args,
        )

    def to_cron_task(self) -> CronTask:
        return CronTask(
            id=self.id,
            path=self.path,
            cron=self.cron,
            enabled=self.enabled,
            args=self.args or {},
        )


class TokenData(BaseModel):
    token: str
    user_id: uuid.UUID
    expires_at: AwareDatetime | None = None
