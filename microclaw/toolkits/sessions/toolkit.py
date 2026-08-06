import datetime
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
        ToolKitCapability.CURRENT_SESSION,
    ]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = []

    def __init__(self, key: str, settings: SessionsToolKitSettings):
        super().__init__(key=key, settings=settings)

    async def _resolve_target_user_id(
        self, ctx, user_id: str | None
    ) -> uuid.UUID | None:
        """Resolve the target user ID for session access.

        If *user_id* is omitted, returns the current user's ID.
        If provided, returns that user's ID after verifying access rights
        (either the current user requests their own sessions, or the toolkit
        context grants ``ALL_USERS`` capability).
        """
        if user_id is None:
            if ctx.current_user_accessor is None:
                return None
            user = await ctx.current_user_accessor.get()
            if user is None:
                return None
            return user.id

        target_id = uuid.UUID(user_id)
        if ctx.current_user_accessor is not None:
            me = await ctx.current_user_accessor.get()
            if me is not None and me.id == target_id:
                return target_id

        if ctx.all_users_accessor is None:
            return None
        user = await ctx.all_users_accessor.get_by_id(target_id)
        if user is None:
            return None
        return user.id

    @tool
    async def search_sessions(
        self, query: str, user_id: str | None = None, limit: int | None = None
    ) -> list[str]:
        """
        Search user sessions for a query.

        Args:
            query: Search query string
            user_id: UUID of the user whose sessions to search. If omitted,
                searches the current user's sessions.
            limit: Maximum number of results to return (default: 10)

        Returns:
            List of session contents matching the query
        """
        ctx = get_toolkit_context()
        if ctx is None or ctx.sessions_accessor is None:
            return []

        target_user_id = await self._resolve_target_user_id(ctx, user_id)
        if target_user_id is None:
            return []

        if ctx.all_users_accessor is None:
            return []

        limit = limit or self._settings.max_results
        results_with_scores = []

        session_gen = ctx.sessions_accessor.get_sessions()
        async for session_id in session_gen:
            owner = await ctx.all_users_accessor.get_by_session(session_id)
            if owner is None or owner.id != target_user_id:
                continue

            content = ""
            messages_gen = ctx.sessions_accessor.get_messages(session_id=session_id)

            async for message in messages_gen:
                content += f"{message.role}: {message.text}\n\n"

            if not content:
                continue

            score = self._calculate_similarity(query, content)
            if score > 0:
                results_with_scores.append((score, content))

        results_with_scores.sort(key=lambda x: x[0], reverse=True)
        return [content for _, content in results_with_scores[:limit]]

    @tool
    async def get_session(
        self, session_id: uuid.UUID, user_id: str | None = None
    ) -> SessionInfo | None:
        """
        Get detailed information about a specific session.

        Args:
            session_id: Unique identifier of the session
            user_id: UUID of the user who owns the session. If omitted,
                uses the current user.

        Returns:
            SessionInfo object with session details or None if not found
        """
        ctx = get_toolkit_context()
        if ctx is None or ctx.sessions_accessor is None:
            return None

        target_user_id = await self._resolve_target_user_id(ctx, user_id)
        if target_user_id is None:
            return None

        if ctx.all_users_accessor is None:
            return None

        owner = await ctx.all_users_accessor.get_by_session(session_id)
        if owner is None or owner.id != target_user_id:
            return None

        messages = []
        messages_gen = ctx.sessions_accessor.get_messages(session_id=session_id)

        async for message in messages_gen:
            messages.append(
                MessageInfo(
                    role=message.role,
                    content=message.text,
                    timestamp=datetime.datetime.now(),
                )
            )

        if not messages:
            return None

        return SessionInfo(
            session_id=session_id,
            messages=messages,
            message_count=len(messages),
            user_id=owner.id if owner else None,
            created_at=None,
            last_activity=None,
        )

    @tool
    async def list_sessions(
        self, user_id: str | None = None, limit: int = 20
    ) -> list[SessionInfo]:
        """
        List all sessions for a user.

        Args:
            user_id: UUID of the user whose sessions to list. If omitted,
                lists the current user's sessions.
            limit: Maximum number of sessions to return (default: 20)

        Returns:
            List of SessionInfo objects with session details
        """
        ctx = get_toolkit_context()
        if ctx is None or ctx.sessions_accessor is None:
            return []

        target_user_id = await self._resolve_target_user_id(ctx, user_id)
        if target_user_id is None:
            return []

        if ctx.all_users_accessor is None:
            return []

        sessions = []

        session_gen = ctx.sessions_accessor.get_sessions()
        async for session_id in session_gen:
            owner = await ctx.all_users_accessor.get_by_session(session_id)
            if owner is None or owner.id != target_user_id:
                continue

            messages = []
            messages_gen = ctx.sessions_accessor.get_messages(session_id=session_id)

            async for message in messages_gen:
                messages.append(
                    MessageInfo(
                        role=message.role,
                        content=message.text,
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
