import uuid

from pydantic import AwareDatetime, BaseModel, Field

from microclaw.dto import CronTask, User, UserRoleEnum


class UserChannelData(BaseModel):
    user_id: uuid.UUID
    sessions: list[uuid.UUID] = Field(default_factory=list)


class UserData(BaseModel):
    id: uuid.UUID
    role: UserRoleEnum = UserRoleEnum.USER
    agent: dict | None = None
    crons: list[CronTask] = Field(default_factory=list)

    @classmethod
    def from_user(cls, user: User) -> "UserData":
        return cls(id=user.id, role=user.role, agent=user.agent, crons=[])

    def to_user(self) -> User:
        return User(id=self.id, role=self.role, agent=self.agent)


class TokenData(BaseModel):
    token: str
    user_id: uuid.UUID
    expires_at: AwareDatetime | None = None
