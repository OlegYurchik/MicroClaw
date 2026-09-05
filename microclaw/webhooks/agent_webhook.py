import json
import uuid

from pydantic import BaseModel, ConfigDict

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.dto import AgentMessage
from microclaw.sessions_storages.dto import SessionCreate
from microclaw.users_storages.dto import UserCreate
from microclaw.users_storages.filters import UserChannelFilter, UserFilter
from microclaw.users_storages.utils import attach_session_to_user
from microclaw.utils import get_by_key_or_first
from microclaw.webhooks.base import BaseWebhook, WebhookResponse


class AgentWebhookSettings(BaseModel):
    agent: str | None = None
    channel: str | None = None
    channel_internal_id: str | None = None
    create_new_session: bool = True


class AgentWebhookPayload(BaseModel):
    text: str | None = None
    model_config = ConfigDict(extra="allow")


class AgentWebhook(BaseWebhook[AgentWebhookSettings, AgentWebhookPayload]):
    async def handle(self, payload: AgentWebhookPayload) -> WebhookResponse | None:
        agents = await self._resolver.resolve_agents()
        agent = get_by_key_or_first(storage=agents, key=self._arguments.agent)
        if agent is None:
            raise RuntimeError(f"Agent not found for webhook: {self._arguments.agent}")

        channel: BaseChannel | None = None
        if self._arguments.channel is not None:
            channels = await self._resolver.resolve_channels()
            channel = get_by_key_or_first(storage=channels, key=self._arguments.channel)
            if channel is None:
                raise RuntimeError(
                    f"Channel not found for webhook: {self._arguments.channel}"
                )

        task_text = payload.text
        if task_text is None:
            task_text = json.dumps(
                payload.model_dump(exclude_none=True), ensure_ascii=False
            )

        new_messages = [
            AgentMessage(
                role="user",
                text=f"Webhook triggered. Please process the following payload:\n\n{task_text}",
            ),
        ]

        if channel is not None:
            await self._execute_with_channel(channel, agent, new_messages)
        else:
            await self._execute_without_channel(agent, new_messages)

        return WebhookResponse(body={"status": "ok"})

    async def _execute_with_channel(
        self,
        channel: BaseChannel,
        agent: Agent,
        new_messages: list[AgentMessage],
    ) -> None:
        if self._arguments.channel is None or self._arguments.channel_internal_id is None:
            raise RuntimeError(
                "Both 'channel' and 'channel_internal_id' must be set for webhook"
            )

        sessions_storage = channel.get_sessions_storage()
        users_storage = channel.get_users_storage()

        user = None
        async for ch in users_storage.get_user_channels(
            filter_=UserChannelFilter(
                channel_key={self._arguments.channel},
                channel_internal_id={self._arguments.channel_internal_id},
            )
        ):
            user = await users_storage.get_user(filter_=UserFilter(id={ch.user_id}))
            break
        if user is None:
            user = await users_storage.create_user(data=UserCreate())

        session_id = None
        async for ch in users_storage.get_user_channels(
            filter_=UserChannelFilter(
                user_id={user.id},
                channel_key={self._arguments.channel},
                channel_internal_id={self._arguments.channel_internal_id},
            )
        ):
            session_id = ch.actual_session_id
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

        await channel.start_conversation(
            channel_internal_id=self._arguments.channel_internal_id,
            session_id=session_id,
            new_messages=new_messages,
            agent=agent,
        )

    async def _execute_without_channel(
        self, agent: Agent, new_messages: list[AgentMessage]
    ) -> None:
        async for _ in agent.ask(messages=new_messages, stream=False):
            pass
