import datetime
import secrets
import uuid
from collections import defaultdict
from typing import AsyncGenerator

from microclaw.dto import CronTask, User, UserChannelID, UserRoleEnum
from microclaw.users_storages.interfaces import UsersStorageInterface
from microclaw.utils import Empty
from .settings import MemoryUsersStorageSettings


class MemoryUsersStorage(UsersStorageInterface):
    def __init__(self, settings: MemoryUsersStorageSettings):
        self._settings = settings
        self._users: dict[uuid.UUID, User] = {}
        self._channels_users: dict[UserChannelID, uuid.UUID] = {}
        self._channel_sessions: defaultdict[UserChannelID, list[uuid.UUID]] = (
            defaultdict(list)
        )
        self._user_crons: dict[uuid.UUID, list[CronTask]] = defaultdict(list)
        self._tokens: dict[str, tuple[uuid.UUID, datetime.datetime | None]] = {}

    async def get_users(self) -> AsyncGenerator[User]:
        for user in self._users.values():
            yield user

    async def create_user(
        self,
        user_id: uuid.UUID | None = None,
        role: UserRoleEnum = UserRoleEnum.USER,
        agent_settings: "AgentSettings | None" = None,  # noqa: F821
    ) -> User:
        if user_id is None:
            user_id = uuid.uuid4()

        user = User(id=user_id, role=role)
        self._users[user_id] = user
        return user

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return self._users.get(user_id)

    async def update_user(
        self,
        user_id: uuid.UUID,
        role: UserRoleEnum | Empty = Empty,
        agent_settings: "AgentSettings | None | Empty" = Empty,  # noqa: F821
    ) -> User | None:
        user = self._users.get(user_id)
        if user is None:
            return None

        if not isinstance(role, Empty):
            user.role = role
        if not isinstance(agent_settings, Empty):
            user.agent = agent_settings

        return user

    async def delete_user(self, user_id: uuid.UUID) -> None:
        if user_id not in self._users:
            return None

        del self._users[user_id]
        to_delete = [
            channel_id
            for channel_id, uid in self._channels_users.items()
            if uid == user_id
        ]
        for channel_id in to_delete:
            del self._channels_users[channel_id]
            if channel_id in self._channel_sessions:
                del self._channel_sessions[channel_id]

        if user_id in self._user_crons:
            del self._user_crons[user_id]

        to_delete_tokens = [
            token for token, (uid, _) in self._tokens.items() if uid == user_id
        ]
        for token in to_delete_tokens:
            del self._tokens[token]

    async def get_user_by_channel(
        self,
        channel_key: str,
        channel_internal_id: str,
    ) -> User | None:
        user_channel_id = UserChannelID(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        user_id = self._channels_users.get(user_channel_id)
        if user_id:
            return self._users.get(user_id)

    async def get_user_by_session(self, session_id: uuid.UUID) -> User | None:
        for user_channel_id, user_id in self._channels_users.items():
            if session_id in self._channel_sessions.get(user_channel_id, []):
                return self._users.get(user_id)

    async def get_user_by_token(self, token: str) -> User | None:
        token_data = self._tokens.get(token)
        if token_data:
            user_id, _ = token_data
            return self._users.get(user_id)
        return None

    async def get_actual_session(
        self,
        user_id: uuid.UUID,
        channel_key: str,
        channel_internal_id: str,
    ) -> uuid.UUID | None:
        user_channel_id = UserChannelID(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        sessions = self._channel_sessions.get(user_channel_id)
        if sessions:
            return sessions[-1]
        return None

    async def attach_session_to_user(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        channel_key: str,
        channel_internal_id: str,
    ) -> None:
        user_channel_id = UserChannelID(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        if user_channel_id not in self._channels_users:
            self._channels_users[user_channel_id] = user_id
        if session_id not in self._channel_sessions[user_channel_id]:
            self._channel_sessions[user_channel_id].append(session_id)

    async def get_crons(self, user_id: uuid.UUID) -> list[CronTask]:
        return self._user_crons.get(user_id, []).copy()

    async def create_cron(
        self,
        user_id: uuid.UUID,
        cron_task: CronTask,
    ) -> None:
        self._user_crons[user_id].append(cron_task)

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        for user_id, crons in self._user_crons.items():
            self._user_crons[user_id] = [cron for cron in crons if cron.id != cron_id]

    async def create_token_for_user(
        self,
        user_id: uuid.UUID,
        ttl: datetime.timedelta | None = datetime.timedelta(days=30),
    ) -> str:
        expires_at = None
        if ttl is not None:
            expires_at = datetime.datetime.now(datetime.timezone.utc) + ttl

        while True:
            token = secrets.token_urlsafe(32)
            if token not in self._tokens:
                break

        self._tokens[token] = (user_id, expires_at)
        return token

    async def delete_token(self, token: str) -> None:
        self._tokens.pop(token, None)
