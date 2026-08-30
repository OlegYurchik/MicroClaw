from typing import Any
import uuid

from .settings import CronSettings
from langgraph.types import interrupt

from microclaw.dto import CronTask, DecisionEnum
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction


class CronToolKit(BaseToolKit[CronSettings]):
    """Tools for managing cron tasks."""

    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = []

    async def _resolve_target_user_id(
        self, ctx, user_id: str | None
    ) -> uuid.UUID | None:
        """Resolve the target user ID for cron operations.

        If *user_id* is omitted, returns the current user's ID.
        If provided, returns that user's ID after verifying access rights
        (either the current user targets themselves, or the toolkit context
        grants ``ALL_USERS`` capability).
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
            raise PermissionError("Cross-user access not granted")
        user = await ctx.all_users_accessor.get_by_id(target_id)
        if user is None:
            raise ValueError(f"User '{user_id}' not found.")
        return user.id

    @tool
    async def get_crons(self, user_id: str | None = None) -> list[CronTask]:
        """
        Get all cron tasks for a user.

        Args:
            user_id: UUID of the user whose crons to retrieve. If omitted,
                returns the current user's cron tasks.

        Returns:
            List of cron tasks with their configuration
        """
        ctx = get_toolkit_context()
        if ctx is None:
            raise RuntimeError("No active channel context")

        if user_id is None:
            if ctx.current_user_accessor is None:
                raise RuntimeError("No active channel context")
            return await ctx.current_user_accessor.get_crons()

        target_id = uuid.UUID(user_id)
        if ctx.current_user_accessor is not None:
            me = await ctx.current_user_accessor.get()
            if me is not None and me.id == target_id:
                return await ctx.current_user_accessor.get_crons()

        if ctx.all_users_accessor is None:
            raise PermissionError("Cross-user access not granted")
        return await ctx.all_users_accessor.get_crons(target_id)

    @tool
    async def create_cron(
        self,
        path: str,
        cron: str,
        enabled: bool = True,
        args: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> CronTask:
        """
        Create a new cron task for a user.

        Args:
            path: Path to the cron task class (e.g., 'microclaw.cron.tasks.agent.AgentCronTask')
            cron: Cron expression (e.g., '0 1 * * *' for daily at 1 AM)
            enabled: Whether the cron task is enabled (default: True)
            args: Arguments for the cron task (default: {})
            user_id: UUID of the target user. If omitted, creates the cron
                task for the current user.

        Returns:
            Created cron task with its ID
        """
        self._require_confirm(
            self.arguments.create_mode,
            f"Create cron task with path '{path}' and schedule '{cron}'?",
        )

        ctx = get_toolkit_context()
        if ctx is None:
            raise RuntimeError("No active channel context")

        target_id = await self._resolve_target_user_id(ctx, user_id)
        if target_id is None:
            raise RuntimeError("No active channel context")

        cron_task = CronTask(
            id=uuid.uuid4(),
            path=path,
            cron=cron,
            enabled=enabled,
            args=args or {},
        )

        if ctx.current_user_accessor is not None:
            me = await ctx.current_user_accessor.get()
            if me is not None and me.id == target_id:
                await ctx.current_user_accessor.create_cron(cron_task)
                return cron_task

        if ctx.all_users_accessor is None:
            raise PermissionError("Cross-user access not granted")
        if not ctx.all_users_accessor.writable:
            raise PermissionError("Cross-user write access not granted")

        await ctx.all_users_accessor.create_cron(target_id, cron_task)
        return cron_task

    @tool
    async def remove_cron(self, cron_id: str, user_id: str | None = None) -> None:
        """
        Remove a cron task by its ID.

        Args:
            cron_id: ID of the cron task to remove (UUID string)
            user_id: UUID of the user who owns the cron task. If omitted,
                removes from the current user.

        Returns:
            None - indicates successful operation
        """
        self._require_confirm(
            self.arguments.delete_mode,
            f"Remove cron task with ID '{cron_id}'?",
        )

        ctx = get_toolkit_context()
        if ctx is None:
            raise RuntimeError("No active channel context")

        cron_uuid = uuid.UUID(cron_id)
        target_id = await self._resolve_target_user_id(ctx, user_id)
        if target_id is None:
            raise RuntimeError("No active channel context")

        if ctx.current_user_accessor is not None:
            me = await ctx.current_user_accessor.get()
            if me is not None and me.id == target_id:
                await ctx.current_user_accessor.remove_cron(cron_uuid)
                return

        if ctx.all_users_accessor is None:
            raise PermissionError("Cross-user access not granted")
        if not ctx.all_users_accessor.writable:
            raise PermissionError("Cross-user write access not granted")

        target_crons = await ctx.all_users_accessor.get_crons(target_id)
        if not any(c.id == cron_uuid for c in target_crons):
            raise ValueError(
                f"Cron task '{cron_id}' not found for user '{target_id}'."
            )

        await ctx.all_users_accessor.remove_cron(cron_uuid)

    def _require_confirm(self, mode: PermissionModeEnum, description: str) -> None:
        """Raise on DENY or when the user rejects a REQUEST confirmation."""
        if mode is PermissionModeEnum.DENY:
            raise PermissionError("Operation denied by configuration")
        if mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": description})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
