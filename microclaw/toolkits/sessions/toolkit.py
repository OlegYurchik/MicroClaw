import uuid
from difflib import SequenceMatcher

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context
from .dto import SessionInfo, MessageInfo
from .settings import SessionsToolKitSettings


class SessionsToolKit(BaseToolKit[SessionsToolKitSettings]):
    required_capabilities = [
        ToolKitCapability.CURRENT_USER,
        ToolKitCapability.ALL_USERS,
        ToolKitCapability.ALL_SESSIONS,
    ]
    write_capabilities = []
    discovery_capabilities = []

    def __init__(self, key: str, settings: SessionsToolKitSettings):
        super().__init__(key=key, settings=settings)

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
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            return []

        user = await ctx.current_user_accessor.get()
        if user is None:
            return []
        user_id = user.id

        if ctx.sessions_accessor is None or ctx.all_users_accessor is None:
            return []

        limit = limit or self._settings.max_results
        results_with_scores = []

        session_gen = ctx.sessions_accessor.get_sessions()
        async for session_id in session_gen:
            owner = await ctx.all_users_accessor.get_by_session(session_id)
            if owner is None or owner.id != user_id:
                continue

            content = ""
            messages_gen = ctx.sessions_accessor.get_messages(session_id=session_id)

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
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            return None

        user = await ctx.current_user_accessor.get()
        if user is None:
            return None
        user_id = user.id

        if ctx.sessions_accessor is None or ctx.all_users_accessor is None:
            return None

        owner = await ctx.all_users_accessor.get_by_session(session_id)
        if owner is None or owner.id != user_id:
            return None

        messages = []
        messages_gen = ctx.sessions_accessor.get_messages(session_id=session_id)

        async for message in messages_gen:
            import datetime

            messages.append(
                MessageInfo(
                    role=message.role,
                    content=message.content,
                    timestamp=datetime.datetime.now(),
                )
            )

        if not messages:
            return None

        return SessionInfo(
            session_id=session_id,
            messages=messages,
            message_count=len(messages),
            created_at=None,
            last_activity=None,
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
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            return []

        user = await ctx.current_user_accessor.get()
        if user is None:
            return []
        user_id = user.id

        if ctx.sessions_accessor is None or ctx.all_users_accessor is None:
            return []

        sessions = []

        session_gen = ctx.sessions_accessor.get_sessions()
        async for session_id in session_gen:
            owner = await ctx.all_users_accessor.get_by_session(session_id)
            if owner is None or owner.id != user_id:
                continue

            messages = []
            messages_gen = ctx.sessions_accessor.get_messages(session_id=session_id)

            async for message in messages_gen:
                import datetime

                messages.append(
                    MessageInfo(
                        role=message.role,
                        content=message.content,
                        timestamp=datetime.datetime.now(),
                    )
                )

            if messages:
                sessions.append(
                    SessionInfo(
                        session_id=session_id,
                        messages=messages,
                        message_count=len(messages),
                        created_at=None,
                        last_activity=None,
                    )
                )

            if len(sessions) >= limit:
                break

        return sessions

    def _calculate_similarity(self, query: str, content: str) -> float:
        matcher = SequenceMatcher(None, query.lower(), content.lower())
        return matcher.ratio()
