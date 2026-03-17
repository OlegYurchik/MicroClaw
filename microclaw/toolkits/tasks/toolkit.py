from datetime import datetime, date

from caldav.aio import AsyncDAVClient, AsyncPrincipal, AsyncCalendar, AsyncTodo
from caldav.elements import dav

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.settings import ToolKitSettings
from .dto import TaskList, Task
from .settings import TasksSettings


class TasksToolKit(BaseToolKit[TasksSettings]):
    """Tools for managing tasks and task lists via Nextcloud Tasks (CalDAV)."""

    def __init__(self, key: str, settings: ToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._client = AsyncDAVClient(
            url=self.settings.url,
            username=self.settings.username,
            password=self.settings.password,
            ssl_verify_cert=self.settings.verify_ssl,
        )
        self._principal = None

    async def get_principal(self) -> AsyncPrincipal:
        if self._principal is None:
            self._principal = await self._client.get_principal()
        return self._principal

    @tool
    async def get_task_lists(self) -> list[TaskList]:
        """
        Get all task lists (calendars) accessible by the user.

        Returns:
            List of TaskList objects with url and name
        """
        principal = await self.get_principal()
        calendars = await principal.get_calendars()
        return [
            await self._convert_calendar_to_dto(calendar=calendar)
            for calendar in calendars
        ]

    @tool
    async def create_task_list(self, name: str) -> TaskList:
        """
        Create a new task list. Use this tool only when user explicitly requests task list creation.

        Args:
            name: Task list name

        Returns:
            TaskList object with url and name
        """
        principal = await self.get_principal()
        calendar = await principal.make_calendar(
            name=name,
            cal_id=None,
            supported_calendar_component_set=None,
        )
        return await self._convert_calendar_to_dto(calendar=calendar)

    @tool
    async def get_task_list(self, url: str) -> TaskList:
        """
        Get task list by url. Use this tool only when user explicitly requests task list details by URL.

        Args:
            url: Task list full url (obtained from get_task_lists or previous interactions)

        Returns:
            TaskList object with url and name
        """
        calendar = AsyncCalendar(client=self._client, url=url)
        name = await calendar.get_property(dav.DisplayName())
        return TaskList(url=url, name=name or "")

    @tool
    async def delete_task_list(self, url: str) -> None:
        """
        Delete a task list. Use this tool only when user explicitly requests task list deletion.

        Args:
            url: Task list full url (obtained from get_task_lists or previous interactions)

        Returns:
            None
        """
        calendar = AsyncCalendar(client=self._client, url=url)
        await calendar.delete()

    @tool
    async def get_tasks(
        self,
        task_list_url: str,
        completed: bool | None = None,
    ) -> list[Task]:
        """
        Get all tasks from a task list.

        Args:
            task_list_url: URL of the task list.
            completed: Optional filter by completion status. None returns all tasks.

        Returns:
            List of Task objects
        """
        calendar = AsyncCalendar(client=self._client, url=task_list_url)
        todos = await calendar.todos(include_completed=completed is None or completed)
        return [
            await self._convert_todo_to_dto(todo=todo)
            for todo in todos
        ]

    @tool
    async def get_task(self, task_uid: str, task_list_url: str) -> Task:
        """
        Get a specific task by its UID.

        Args:
            task_uid: Unique identifier of the task
            task_list_url: URL of the task list.

        Returns:
            Task object
        """
        calendar = AsyncCalendar(client=self._client, url=task_list_url)
        todo = await calendar.todo_by_uid(task_uid)
        if not todo:
            raise ValueError(f"Task with UID {task_uid} not found")
        return await self._convert_todo_to_dto(todo=todo)

    @tool
    async def create_task(
        self,
        summary: str,
        task_list_url: str,
        description: str | None = None,
        due: str | None = None,
        priority: int | None = None,
        
    ) -> Task:
        """
        Create a new task. Use this tool when user wants to add a new task.

        Args:
            summary: Title/summary of the task
            description: Optional description of the task
            due: Optional due date in ISO format (e.g., "2024-12-31" or "2024-12-31T23:59:59")
            priority: Optional priority level (1=highest, 9=lowest, 0=undefined)
            task_list_url: URL of the task list.

        Returns:
            Created Task object
        """
        calendar = AsyncCalendar(client=self._client, url=task_list_url)
        todo_data = {"summary": summary}
        if description:
            todo_data["description"] = description
        if due:
            todo_data["due"] = due
        if priority is not None:
            todo_data["priority"] = priority

        todo = await calendar.add_todo(**todo_data)
        return await self._convert_todo_to_dto(todo=todo)

    @tool
    async def update_task(
            self,
            task_uid: str,
            task_list_url: str,
            summary: str | None = None,
            description: str | None = None,
            due: str | None = None,
            priority: int | None = None,
            completed: bool | None = None,
    ) -> Task:
        """
        Update an existing task. Use this tool when user wants to modify a task.

        Args:
            task_uid: Unique identifier of the task
            summary: Optional new title/summary of the task
            description: Optional new description of the task
            due: Optional new due date in ISO format
            priority: Optional new priority level (1=highest, 9=lowest, 0=undefined)
            completed: Optional new completion status
            task_list_url: URL of the task list.

        Returns:
            Updated Task object
        """
        calendar = AsyncCalendar(client=self._client, url=task_list_url)

        todo = await calendar.todo_by_uid(task_uid)
        if not todo:
            raise ValueError(f"Task with UID {task_uid} not found")

        if summary is not None:
            todo.vobject_instance.vtodo.summary.value = summary
        if description is not None:
            todo.vobject_instance.vtodo.description.value = description
        if due is not None:
            todo.vobject_instance.vtodo.due.value = due
        if priority is not None:
            todo.vobject_instance.vtodo.priority.value = priority
        if completed is not None:
            if completed:
                todo.vobject_instance.vtodo.add("status").value = "COMPLETED"
                todo.vobject_instance.vtodo.add("completed").value = datetime.now()
            else:
                if hasattr(todo.vobject_instance.vtodo, "status"):
                    del todo.vobject_instance.vtodo.status
                if hasattr(todo.vobject_instance.vtodo, "completed"):
                    del todo.vobject_instance.vtodo.completed

        await todo.save()
        return await self._convert_todo_to_dto(todo=todo)

    @tool
    async def delete_task(self, task_uid: str, task_list_url: str) -> None:
        """
        Delete a task. Use this tool only when user explicitly requests task deletion.

        Args:
            task_uid: Unique identifier of the task
            task_list_url: URL of the task list.

        Returns:
            None
        """
        calendar = AsyncCalendar(client=self._client, url=task_list_url)

        todo = await calendar.todo_by_uid(task_uid)
        if not todo:
            raise ValueError(f"Task with UID {task_uid} not found")
        await todo.delete()

    @tool
    async def complete_task(self, task_uid: str, task_list_url: str) -> Task:
        """
        Mark a task as completed. Use this tool when user wants to mark a task as done.

        Args:
            task_uid: Unique identifier of the task
            task_list_url: URL of the task list.

        Returns:
            Updated Task object
        """
        return await self.update_task(
            task_uid=task_uid,
            completed=True,
            task_list_url=task_list_url,
        )

    async def _convert_calendar_to_dto(self, calendar: AsyncCalendar) -> TaskList:
        name = await calendar.get_property(dav.DisplayName())
        return TaskList(url=calendar.url, name=name or "")

    async def _convert_todo_to_dto(self, todo: AsyncTodo) -> Task:
        vtodo = todo.vobject_instance.vtodo

        summary = getattr(vtodo, "summary", None)
        summary_value = summary.value if summary else ""

        description = getattr(vtodo, "description", None)
        description_value = description.value if description else None

        status = getattr(vtodo, "status", None)
        status_value = status.value if status else None

        priority = getattr(vtodo, "priority", None)
        priority_value = priority.value if priority else None

        due = getattr(vtodo, "due", None)
        due_value = due.value if due else None

        dtstart = getattr(vtodo, "dtstart", None)
        start_value = dtstart.value if dtstart else None

        completed = getattr(vtodo, "completed", None)
        completed_value = completed.value if completed else None

        created = getattr(vtodo, "created", None)
        created_value = created.value if created else None

        last_modified = getattr(vtodo, "last-modified", None)
        modified_value = last_modified.value if last_modified else None

        percent_complete = getattr(vtodo, "percent-complete", None)
        percent_value = percent_complete.value if percent_complete else None

        categories = getattr(vtodo, "categories", None)
        categories_list = list(categories.value) if categories else []

        return Task(
            uid=todo.id,
            url=todo.url,
            summary=summary_value,
            description=description_value,
            status=status_value,
            priority=priority_value,
            due=due_value,
            start=start_value,
            completed=completed_value is not None,
            completed_at=completed_value,
            created=created_value,
            modified=modified_value,
            percent_complete=percent_value,
            categories=categories_list,
        )
