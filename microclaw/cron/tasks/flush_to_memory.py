import datetime
import uuid

from loguru import logger
from pydantic import BaseModel
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.channels.base import BaseChannel
from microclaw.cron.base import BaseCronTask
from microclaw.cron.settings import CronTaskSettings
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.sessions_storages.filters import SessionFilter, MessageFilter
from microclaw.toolkits.memory.toolkit import MemorySizeExceeded
from microclaw.utils import get_by_key_or_first


class FlushToMemoryCronTaskSettings(BaseModel):
    pass


class FlushToMemoryCronTask(BaseCronTask[FlushToMemoryCronTaskSettings]):
    def __init__(
            self,
            key: str,
            settings: CronTaskSettings,
            resolver: "DependencyResolver",  # noqa: F821
    ):
        super().__init__(key=key, settings=settings, resolver=resolver)
        self._sessions_storage: SessionsStorageInterface | None = None
        self._channels: dict[str, BaseChannel] | None = None
    
    async def do_before(self):
        sessions_storages = await self._resolver.resolve_sessions_storages()
        self._sessions_storage = get_by_key_or_first(storage=sessions_storages)
        if self._sessions_storage is None:
            raise RuntimeError(f"Sessions storage not found for task '{self._key}'")
        
        self._channels = await self._resolver.resolve_channels()
        if not self._channels:
            raise RuntimeError(f"No channels found for task '{self._key}'")
    
    async def execute(self):
        logger.info(f"Running daily task '{self._key}'")
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        await self._process_day(yesterday)
    
    async def _process_day(self, date: datetime.date):
        all_extracted_info = []
        
        async for session_id in self._sessions_storage.get_sessions(filter=SessionFilter(created_at=date)):
            user = await self._get_user_by_session(session_id)
            if user is None:
                logger.warning(f"User not found for session {session_id}")
                continue

            channel = await self._get_channel_for_user(user)
            if channel is None:
                logger.warning(f"Channel not found for user {user.id}")
                continue

            agent = await channel.get_agent_for_user(user)
            if agent is None:
                logger.warning(f"Agent not found for user {user.id}")
                continue

            messages = []
            async for message in self._sessions_storage.get_messages(
                filter=MessageFilter(session_id=session_id),
                from_last_summarization=False,
            ):
                messages.append(message)
            
            if not messages:
                continue
            
            extracted_info = await agent.extract_important_info(
                messages=messages,
                max_tokens=agent.get_max_memory_flush_tokens(),
                is_daily=True,
            )

            if extracted_info:
                all_extracted_info.append(extracted_info)

        if not all_extracted_info:
            logger.info(f"No sessions found for date {date}")
            return
        
        combined_info = "\n\n".join(all_extracted_info)
        
        agent = get_by_key_or_first(storage=await self._resolver.resolve_agents())
        if agent is None:
            logger.error("No agent available for memory summarization")
            return

        memory_toolkit = agent.get_memory_toolkit()
        if memory_toolkit is None:
            logger.warning("Memory toolkit not found, skipping daily memory processing")
            return

        old_memory = await memory_toolkit.get_memory(date=date) or ""
        
        if old_memory:
            response = await agent.summarize_memory(
                old_context=old_memory,
                new_context=combined_info,
                is_daily=True,
            )
            new_memory = response.content.strip()
        else:
            new_memory = combined_info
        
        try:
            await memory_toolkit.append_to_memory(content=new_memory, date=date)
        except MemorySizeExceeded:
            response = await agent.summarize_memory(
                old_context=old_memory,
                new_context=combined_info,
                is_daily=True,
            )
            await memory_toolkit.rewrite_memory(
                content=response.content.strip(),
                date=date,
            )
        
        logger.info(f"Daily memory processing completed for date {date}")
    
    async def _get_user_by_session(self, session_id: uuid.UUID):
        for channel in self._channels.values():
            users_storage = channel.get_users_storage()
            user = await users_storage.get_user_by_session(session_id)
            if user is not None:
                return user

    async def _get_channel_for_user(self, user):
        for channel in self._channels.values():
            users_storage = channel.get_users_storage()
            check_user = await users_storage.get_user(user.id)
            if check_user is not None:
                return channel
