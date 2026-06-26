import logging
import uuid

from pydantic import BaseModel

from microclaw.agents import Agent, AgentSettings
from microclaw.channels.base import BaseChannel
from microclaw.dto import AgentMessage
from microclaw.cron.base import BaseCronTask
from microclaw.cron.settings import CronTaskSettings
from microclaw.utils import get_by_key_or_first


logger = logging.getLogger(__name__)


class AgentCronTaskSettings(BaseModel):
    task: str
    channel: str
    channel_internal_id: str
    agent: str | AgentSettings | None = None
    create_new_session: bool = True


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
        channels = await self._resolver.resolve_channels()
        self._channel = get_by_key_or_first(storage=channels, key=self._settings.channel)
        if self._channel is None:
            raise RuntimeError(f"Channel not found for task '{self._key}'")
        
        if self._settings.agent is not None:
            if isinstance(self._settings.agent, str):
                agents = await self._resolver.resolve_agents()
                self._agent = get_by_key_or_first(storage=agents, key=self._settings.agent)
                if self._agent is None:
                    raise RuntimeError(f"Agent not found for task '{self._key}'")
            elif isinstance(self._settings.agent, AgentSettings):
                self._agent = await self._resolver.resolve_agent(agent_settings=self._settings.agent)
    
    async def execute(self):
        logger.info(f"Run scheduled task '{self._key}'")

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

        task_text = (
            "This is an automated scheduled task triggered by cron. "
            "Please execute the following instruction accordingly.\n\n"
            f"{self._settings.task}"
        )
        new_messages = [
            AgentMessage(role="user", text=task_text),
        ]

        await self._channel.start_conversation(
            channel_internal_id=self._settings.channel_internal_id,
            session_id=session_id,
            new_messages=new_messages,
            agent=self._agent,
        )
