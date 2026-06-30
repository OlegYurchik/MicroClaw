import uuid

from loguru import logger
from pydantic import BaseModel, model_validator

from microclaw.agents import Agent, AgentSettings
from microclaw.channels.base import BaseChannel
from microclaw.dto import AgentMessage
from microclaw.cron.base import BaseCronTask
from microclaw.cron.settings import CronTaskSettings
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
        if self._settings.channel is not None:
            channels = await self._resolver.resolve_channels()
            self._channel = get_by_key_or_first(storage=channels, key=self._settings.channel)
            if self._channel is None:
                raise RuntimeError(f"Channel not found for task '{self._key}'")

        agents = await self._resolver.resolve_agents()
        if isinstance(self._settings.agent, AgentSettings):
            self._agent = await self._resolver.resolve_agent(agent_settings=self._settings.agent)
        else:
            self._agent = get_by_key_or_first(storage=agents, key=self._settings.agent)

        if self._agent is None:
            raise RuntimeError(f"Agent not found for task '{self._key}'")

    async def execute(self):
        logger.info(f"Run scheduled task '{self._key}'")

        task_text = (
            "This is an automated scheduled task triggered by cron. "
            "Please execute the following instruction accordingly.\n\n"
            f"{self._settings.task}"
        )
        new_messages = [
            AgentMessage(role="user", text=task_text),
        ]
        if self._channel is not None:
            await self._execute_with_channel(new_messages)
        else:
            await self._execute_without_channel(new_messages)

    async def _execute_with_channel(self, new_messages: list[AgentMessage]):
        if self._settings.channel is None or self._settings.channel_internal_id is None:
            raise RuntimeError(
                f"Channel and channel_internal_id must be set for task '{self._key}'"
            )

        sessions_storage = self._channel.get_sessions_storage()
        users_storage = self._channel.get_users_storage()

        user = await users_storage.get_user_by_channel(
            channel_key=self._settings.channel,
            channel_internal_id=self._settings.channel_internal_id,
        )
        if user is None:
            user = await users_storage.create_user()

        session_id = await users_storage.get_actual_session(
            user_id=user.id,
            channel_key=self._settings.channel,
            channel_internal_id=self._settings.channel_internal_id,
        )
        if self._settings.create_new_session or session_id is None:
            session_id = uuid.uuid4()
            await sessions_storage.create_session(session_id=session_id)
            await users_storage.attach_session_to_user(
                user_id=user.id,
                session_id=session_id,
                channel_key=self._settings.channel,
                channel_internal_id=self._settings.channel_internal_id,
            )

        await self._channel.start_conversation(
            channel_internal_id=self._settings.channel_internal_id,
            session_id=session_id,
            new_messages=new_messages,
            agent=self._agent,
        )

    async def _execute_without_channel(self, new_messages: list[AgentMessage]):
        async for _ in self._agent.ask(messages=new_messages, stream=False):
            pass
