from langgraph.types import interrupt
import uuid
from typing import Any

from microclaw.dto import DecisionEnum
from microclaw.dto import CronTask
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
from .settings import CronSettings


class CronToolKit(BaseToolKit[CronSettings]):
    """Tools for managing cron tasks."""

    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = []

    @tool
    async def get_crons(self) -> list[CronTask]:
        """
        Get all cron tasks for the current user.

        Returns:
            List of cron tasks with their configuration
        """
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("No active channel context")
        return await ctx.current_user_accessor.get_crons()

    @tool
    async def create_cron(
        self,
        path: str,
        cron: str,
        enabled: bool = True,
        args: dict[str, Any] | None = None,
    ) -> CronTask:
        """
        Create a new cron task for the current user.

        Args:
            path: Path to the cron task class (e.g., 'microclaw.cron.tasks.agent.AgentCronTask')
            cron: Cron expression (e.g., '0 1 * * *' for daily at 1 AM)
            enabled: Whether the cron task is enabled (default: True)
            args: Arguments for the cron task (default: {})

        Returns:
            Created cron task with its ID
        """
        if self.settings.create_mode is PermissionModeEnum.DENY:
            raise PermissionError("Create operations denied")
        if self.settings.create_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = (
                f"Create cron task with path '{path}' and schedule '{cron}'?"
            )
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("No active channel context")

        cron_task = CronTask(
            id=uuid.uuid4(),
            path=path,
            cron=cron,
            enabled=enabled,
            args=args or {},
        )

        await ctx.current_user_accessor.create_cron(cron_task)
        return cron_task

    @tool
    async def remove_cron(self, cron_id: str) -> None:
        """
        Remove a cron task by its ID.

        Args:
            cron_id: ID of the cron task to remove (UUID string)

        Returns:
            None - indicates successful operation
        """
        if self.settings.delete_mode is PermissionModeEnum.DENY:
            raise PermissionError("Delete operations denied")
        if self.settings.delete_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Remove cron task with ID '{cron_id}'?"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("No active channel context")

        cron_uuid = uuid.UUID(cron_id)
        await ctx.current_user_accessor.remove_cron(cron_uuid)
