from microclaw.dto import DecisionEnum
from langgraph.types import interrupt
import uuid
from typing import Any

from microclaw.channels import BaseChannel
from microclaw.dto import CronTask
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
from .settings import CronSettings


class CronToolKit(BaseToolKit[CronSettings]):
    """Tools for managing cron tasks."""

    @tool
    async def get_crons(self) -> list[CronTask]:
        """
        Get all cron tasks for the current user.

        Returns:
            List of cron tasks with their configuration
        """
        users_storage = self._get_users_storage()
        user_id = self._get_user_id()

        cron_tasks = await users_storage.get_crons(user_id=user_id)

        return cron_tasks

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

        users_storage = self._get_users_storage()
        user_id = self._get_user_id()

        cron_task = CronTask(
            id=uuid.uuid4(),
            path=path,
            cron=cron,
            enabled=enabled,
            args=args or {},
        )

        await users_storage.create_cron(user_id=user_id, cron_task=cron_task)
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

        users_storage = self._get_users_storage()

        cron_uuid = uuid.UUID(cron_id)
        await users_storage.remove_cron(cron_id=cron_uuid)

    def _get_users_storage(self):
        channel = BaseChannel.get_current_channel()
        if channel is None:
            raise RuntimeError("No active channel found")
        return channel.get_users_storage()

    def _get_user_id(self) -> uuid.UUID:
        channel = BaseChannel.get_current_channel()
        if channel is None:
            raise RuntimeError("No active channel found")
        return channel.get_user_id()
