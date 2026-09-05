import uuid

from loguru import logger
from pydantic import BaseModel, model_validator

from microclaw.agents import Agent, AgentSettings
from microclaw.channels.base import BaseChannel
from microclaw.cron.base import BaseCronTask
from microclaw.cron.settings import CronTaskSettings
from microclaw.dto import AgentMessage, AgentMessageRoleEnum
from microclaw.sessions_storages.dto import SessionCreate
from microclaw.users_storages.dto import UserCreate
from microclaw.users_storages.filters import UserChannelFilter, UserFilter
from microclaw.users_storages.utils import attach_session_to_user
from microclaw.utils import get_by_key_or_first


class AgentCronTaskSettings(BaseModel):
    task: str
    channel: str | None = None
    channel_internal_id: str | None = None
    agent: str | AgentSettings | None = None
    create_new_session: bool = True

    @model_validator(mode="after")
    def validate_channel_args(self):
        if (self.channel is None) != (self.channel_internal_id is None):
            raise ValueError(
                "Both 'channel' and 'channel_internal_id' must be either set or None."
            )
        return self


class AgentCronTask(BaseCronTask[AgentCronTaskSettings]):
    def __init__(
        self,
        key: str,
        settings: CronTaskSettings,
        resolver: "DependencyResolver",  # noqa: F821
    ):
        super().__init__(key=key, settings=settings, resolver=resolver)
        self._channel: BaseChannel | None = None
        self._agent: Agent | None = None

    async def do_before(self):
        if self._arguments.channel is not None:
            channels = await self._resolver.resolve_channels()
            self._channel = get_by_key_or_first(
                storage=channels, key=self._arguments.channel
            )
            if self._channel is None:
                raise RuntimeError(f"Channel not found for task '{self._key}'")

        agents = await self._resolver.resolve_agents()
        if isinstance(self._arguments.agent, AgentSettings):
            self._agent = await self._resolver.resolve_agent(
                agent_settings=self._arguments.agent
            )
        else:
            self._agent = get_by_key_or_first(storage=agents, key=self._arguments.agent)

        if self._agent is None:
            raise RuntimeError(f"Agent not found for task '{self._key}'")

    async def execute(self):
        logger.info(f"Run scheduled task '{self._key}'")

        task_text = (
            "This is an automated scheduled task triggered by cron. "
            "Please execute the following instruction accordingly.\n\n"
            f"{self._arguments.task}"
        )
        new_messages = [
            AgentMessage(role=AgentMessageRoleEnum.USER, text=task_text),
        ]
        if self._channel is not None:
            await self._execute_with_channel(new_messages)
        else:
            await self._execute_without_channel(new_messages)

    async def _execute_with_channel(self, new_messages: list[AgentMessage]):
        if self._arguments.channel is None or self._arguments.channel_internal_id is None:
            raise RuntimeError(
                f"Channel and channel_internal_id must be set for task '{self._key}'"
            )

        sessions_storage = self._channel.get_sessions_storage()
        users_storage = self._channel.get_users_storage()

        user = None
        async for user_channel in users_storage.get_user_channels(
            filter_=UserChannelFilter(
                channel_key={self._arguments.channel},
                channel_internal_id={self._arguments.channel_internal_id},
            )
        ):
            user = await users_storage.get_user(
                filter_=UserFilter(id={user_channel.user_id})
            )
            break
        if user is None:
            user = await users_storage.create_user(data=UserCreate())

        session_id = None
        async for user_channel in users_storage.get_user_channels(
            filter_=UserChannelFilter(
                user_id={user.id},
                channel_key={self._arguments.channel},
                channel_internal_id={self._arguments.channel_internal_id},
            )
        ):
            session_id = user_channel.actual_session_id
            break
        if self._arguments.create_new_session or session_id is None:
            session_id = uuid.uuid4()
            await sessions_storage.create_session(
                data=SessionCreate(
                    id=session_id,
                    channel_key=self._arguments.channel,
                    channel_internal_id=self._arguments.channel_internal_id,
                )
            )
            await attach_session_to_user(
                storage=users_storage,
                user_id=user.id,
                session_id=session_id,
                channel_key=self._arguments.channel,
                channel_internal_id=self._arguments.channel_internal_id,
            )

        await self._channel.start_conversation(
            channel_internal_id=self._arguments.channel_internal_id,
            session_id=session_id,
            new_messages=new_messages,
            agent=self._agent,
        )

    async def _execute_without_channel(self, new_messages: list[AgentMessage]):
        async for _ in self._agent.ask(messages=new_messages, stream=False):
            pass
