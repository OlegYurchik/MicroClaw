from typing import Any
import uuid

from .settings import UsersToolKitSettings

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context


class UsersToolKit(BaseToolKit[UsersToolKitSettings]):
    """Tools for working with user profiles."""

    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = []

    @tool
    async def get_my_profile(self) -> dict[str, Any] | None:
        """Get current user profile information (id, role, agent overrides)."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        if user is None:
            return None
        return user.model_dump(mode="json")

    @tool
    async def list_users(self, limit: int = 100) -> list[dict[str, Any]]:
        """List all registered users. Requires ALL_USERS capability."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.all_users_accessor is None:
            return []
        result = []
        async for user in ctx.all_users_accessor.get_users():
            result.append(user.model_dump(mode="json"))
            if len(result) >= limit:
                break
        return result

    @tool
    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get a specific user's profile by ID. Requires ALL_USERS capability."""
        ctx = get_toolkit_context()
        if ctx is None:
            return None

        # Allow reading own profile without ALL_USERS
        target_id = uuid.UUID(user_id)
        if ctx.current_user_accessor is not None:
            me = await ctx.current_user_accessor.get()
            if me is not None and me.id == target_id:
                return me.model_dump(mode="json")

        if ctx.all_users_accessor is None:
            return None
        user = await ctx.all_users_accessor.get_by_id(target_id)
        if user is None:
            return None
        return user.model_dump(mode="json")

    @tool
    async def get_user_by_session(self, session_id: str) -> dict[str, Any] | None:
        """Find the user who owns a given session. Requires ALL_USERS capability."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.all_users_accessor is None:
            return None
        user = await ctx.all_users_accessor.get_by_session(uuid.UUID(session_id))
        if user is None:
            return None
        return user.model_dump(mode="json")
