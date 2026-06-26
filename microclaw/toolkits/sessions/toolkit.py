import uuid
from difflib import SequenceMatcher

from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.channels import BaseChannel
from microclaw.sessions_storages.filters import SessionFilter, MessageFilter
from .dto import SessionInfo, MessageInfo, SearchResult
from .settings import SessionsToolKitSettings


class SessionsToolKit(BaseToolKit[SessionsToolKitSettings]):
    def __init__(self, key: str, settings: SessionsToolKitSettings):
        super().__init__(key=key, settings=settings)

    def _get_current_user_id(self) -> uuid.UUID | None:
        channel = BaseChannel.get_current_channel()
        if channel is None:
            return None
        return channel.get_user_id()

    def _get_sessions_storage(self):
        channel = BaseChannel.get_current_channel()
        if channel is None:
            return None
        return channel.get_sessions_storage()

    def _get_users_storage(self):
        channel = BaseChannel.get_current_channel()
        if channel is None:
            return None
        return channel.get_users_storage()

    @tool
    async def search_sessions(self, query: str, limit: int | None = None) -> list[str]:
        """
        Search user sessions for a query.

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 10)

        Returns:
            List of session contents matching the query
        """
        user_id = self._get_current_user_id()
        if user_id is None:
            return []

        sessions_storage = self._get_sessions_storage()
        users_storage = self._get_users_storage()
        if sessions_storage is None or users_storage is None:
            return []

        limit = limit or self._settings.max_results
        results_with_scores = []

        session_gen = sessions_storage.get_sessions()
        async for session_id in session_gen:
            user = await users_storage.get_user_by_session(session_id)
            if user is None or user.id != user_id:
                continue

            content = ""
            messages_gen = sessions_storage.get_messages(filter=MessageFilter(session_id=session_id))
            
            async for message in messages_gen:
                content += f"{message.role}: {message.content}\n\n"

            if not content:
                continue

            score = self._calculate_similarity(query, content)
            if score > 0:
                results_with_scores.append((score, content))

        results_with_scores.sort(key=lambda x: x[0], reverse=True)
        return [content for _, content in results_with_scores[:limit]]

    @tool
    async def get_session(self, session_id: uuid.UUID) -> SessionInfo | None:
        """
        Get detailed information about a specific session.

        Args:
            session_id: Unique identifier of the session

        Returns:
            SessionInfo object with session details or None if not found
        """
        user_id = self._get_current_user_id()
        if user_id is None:
            return None

        sessions_storage = self._get_sessions_storage()
        users_storage = self._get_users_storage()
        if sessions_storage is None or users_storage is None:
            return None

        user = await users_storage.get_user_by_session(session_id)
        if user is None or user.id != user_id:
            return None

        messages = []
        messages_gen = sessions_storage.get_messages(filter=MessageFilter(session_id=session_id))
        
        async for message in messages_gen:
            import datetime
            messages.append(MessageInfo(
                role=message.role,
                content=message.content,
                timestamp=datetime.datetime.now()
            ))

        if not messages:
            return None

        return SessionInfo(
            session_id=session_id,
            messages=messages,
            message_count=len(messages),
            created_at=None,
            last_activity=None
        )

    @tool
    async def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        """
        List all sessions for the current user.

        Args:
            limit: Maximum number of sessions to return (default: 20)

        Returns:
            List of SessionInfo objects with session details
        """
        user_id = self._get_current_user_id()
        if user_id is None:
            return []

        sessions_storage = self._get_sessions_storage()
        users_storage = self._get_users_storage()
        if sessions_storage is None or users_storage is None:
            return []

        sessions = []

        session_gen = sessions_storage.get_sessions()
        async for session_id in session_gen:
            user = await users_storage.get_user_by_session(session_id)
            if user is None or user.id != user_id:
                continue

            messages = []
            messages_gen = sessions_storage.get_messages(filter=MessageFilter(session_id=session_id))
            
            async for message in messages_gen:
                import datetime
                messages.append(MessageInfo(
                    role=message.role,
                    content=message.content,
                    timestamp=datetime.datetime.now()
                ))

            if messages:
                sessions.append(SessionInfo(
                    session_id=session_id,
                    messages=messages,
                    message_count=len(messages),
                    created_at=None,
                    last_activity=None
                ))

            if len(sessions) >= limit:
                break

        return sessions

    def _calculate_similarity(self, query: str, content: str) -> float:
        matcher = SequenceMatcher(None, query.lower(), content.lower())
        return matcher.ratio()
