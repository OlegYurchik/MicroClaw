from datetime import datetime, timezone

import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.tasks.dto import TaskList
from microclaw.toolkits.tasks.toolkit import TasksToolKit
from tests.toolkits.fake_caldav_client import FakeAsyncDAVClient


class TestTasksToolKit:
    @pytest.fixture
    def toolkit(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.tasks.toolkit.TasksToolKit",
            args={"url": "http://test", "username": "u", "password": "p"},
        )
        return TasksToolKit(key="tasks", settings=settings, client=FakeAsyncDAVClient())

    @pytest.mark.asyncio
    async def test_get_task_lists_success(self, toolkit):
        result = await toolkit.get_task_lists()
        assert len(result) == 1
        assert result[0].name == "My Tasks"

    @pytest.mark.asyncio
    async def test_get_task_lists_filtered(self, toolkit):
        toolkit.arguments.allowed_task_lists = ["Other Tasks"]
        result = await toolkit.get_task_lists()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_create_task_list_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.create_task_list(name="New List")
        assert isinstance(result, TaskList)
        assert result.name == "My Tasks"

    @pytest.mark.asyncio
    async def test_create_task_list_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.create_task_list(name="New List")

    @pytest.mark.asyncio
    async def test_get_task_list_success(self, toolkit):
        result = await toolkit.get_task_list(url="http://test/calendars/tasks/")
        assert result.name == "My Tasks"

    @pytest.mark.asyncio
    async def test_delete_task_list_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.delete_task_list(url="http://test/calendars/tasks/")

    @pytest.mark.asyncio
    async def test_delete_task_list_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.delete_task_list(url="http://test/calendars/tasks/")

    @pytest.mark.asyncio
    async def test_delete_task_list_not_allowed(self, toolkit):
        toolkit.arguments.allowed_task_lists = ["Other Tasks"]
        with pytest.raises(PermissionError):
            await toolkit.delete_task_list(url="http://test/calendars/tasks/")

    @pytest.mark.asyncio
    async def test_get_tasks_success(self, toolkit):
        result = await toolkit.get_tasks(task_list_url="http://test/calendars/tasks/")
        assert len(result) == 1
        assert result[0].summary == "Test Task"
        assert result[0].completed is False

    @pytest.mark.asyncio
    async def test_get_tasks_completed_filter(self, toolkit):
        result = await toolkit.get_tasks(
            task_list_url="http://test/calendars/tasks/", completed=True
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_tasks_overdue_filter(self, toolkit):
        result = await toolkit.get_tasks(
            task_list_url="http://test/calendars/tasks/", overdue=True
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_task_success(self, toolkit):
        result = await toolkit.get_task(
            task_uid="todo-1", task_list_url="http://test/calendars/tasks/"
        )
        assert result.summary == "Test Task"

    @pytest.mark.asyncio
    async def test_create_task_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.create_task(
            summary="New Task",
            task_list_url="http://test/calendars/tasks/",
            description="A desc",
            due=datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc),
            start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            priority=1,
        )
        assert result.summary == "New Task"

    @pytest.mark.asyncio
    async def test_create_task_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.create_task(
                summary="New Task",
                task_list_url="http://test/calendars/tasks/",
            )

    @pytest.mark.asyncio
    async def test_update_task_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.update_task(
            task_uid="todo-1",
            task_list_url="http://test/calendars/tasks/",
            summary="Updated Task",
        )
        assert result.summary == "Updated Task"

    @pytest.mark.asyncio
    async def test_update_task_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.update_task(
                task_uid="todo-1",
                task_list_url="http://test/calendars/tasks/",
                summary="Updated Task",
            )

    @pytest.mark.asyncio
    async def test_delete_task_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.delete_task(
            task_uid="todo-1", task_list_url="http://test/calendars/tasks/"
        )

    @pytest.mark.asyncio
    async def test_delete_task_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.delete_task(
                task_uid="todo-1", task_list_url="http://test/calendars/tasks/"
            )

    @pytest.mark.asyncio
    async def test_complete_task_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.complete_task(
            task_uid="todo-1", task_list_url="http://test/calendars/tasks/"
        )
        assert result.completed is True

    @pytest.mark.asyncio
    async def test_complete_task_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.complete_task(
                task_uid="todo-1", task_list_url="http://test/calendars/tasks/"
            )
