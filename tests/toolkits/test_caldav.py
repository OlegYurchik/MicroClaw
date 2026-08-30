from datetime import date, datetime, timezone

import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.caldav.dto import Calendar, Reminder
from microclaw.toolkits.caldav.toolkit import CalDAVToolKit
from microclaw.toolkits.enums import PermissionModeEnum
from tests.toolkits.fake_caldav_client import FakeAsyncDAVClient


class TestCalDAVToolKit:
    @pytest.fixture
    def toolkit(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.caldav.toolkit.CalDAVToolKit",
            args={"url": "http://test", "username": "u", "password": "p"},
        )
        return CalDAVToolKit(
            key="caldav", settings=settings, client=FakeAsyncDAVClient()
        )

    @pytest.mark.asyncio
    async def test_list_calendars_success(self, toolkit):
        result = await toolkit.get_calendars()
        assert len(result) == 1
        assert result[0].name == "My Tasks"

    @pytest.mark.asyncio
    async def test_list_calendars_filtered(self, toolkit):
        toolkit.arguments.allowed_calendars = ["Other Calendar"]
        result = await toolkit.get_calendars()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_create_calendar_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.create_calendar(name="New Calendar")
        assert isinstance(result, Calendar)
        assert result.name == "My Tasks"

    @pytest.mark.asyncio
    async def test_create_calendar_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.create_calendar(name="New Calendar")

    @pytest.mark.asyncio
    async def test_get_calendar_success(self, toolkit):
        result = await toolkit.get_calendar(url="http://test/calendars/tasks/")
        assert result.name == "My Tasks"

    @pytest.mark.asyncio
    async def test_delete_calendar_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.delete_calendar(url="http://test/calendars/tasks/")

    @pytest.mark.asyncio
    async def test_delete_calendar_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.delete_calendar(url="http://test/calendars/tasks/")

    @pytest.mark.asyncio
    async def test_delete_calendar_not_allowed(self, toolkit):
        toolkit.arguments.allowed_calendars = ["Other Calendar"]
        with pytest.raises(PermissionError):
            await toolkit.delete_calendar(url="http://test/calendars/tasks/")

    @pytest.mark.asyncio
    async def test_get_events_success(self, toolkit):
        result = await toolkit.get_events(calendar_url="http://test/calendars/tasks/")
        assert len(result) == 1
        assert result[0].summary == "Test Event"

    @pytest.mark.asyncio
    async def test_get_events_date_range(self, toolkit):
        start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc).isoformat()
        end = datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc).isoformat()
        result = await toolkit.get_events(
            calendar_url="http://test/calendars/tasks/", start=start, end=end
        )
        assert len(result) == 1
        assert result[0].summary == "Test Event"

    @pytest.mark.asyncio
    async def test_get_events_all_calendars(self, toolkit):
        result = await toolkit.get_events()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_create_event_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
        result = await toolkit.create_event(
            calendar_url="http://test/calendars/tasks/",
            summary="New Event",
            start=start,
            end=end,
            description="A desc",
            location="Somewhere",
            all_day=False,
        )
        assert result.summary == "New Event"

    @pytest.mark.asyncio
    async def test_create_event_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
        with pytest.raises(PermissionError):
            await toolkit.create_event(
                calendar_url="http://test/calendars/tasks/",
                summary="New Event",
                start=start,
                end=end,
            )

    @pytest.mark.asyncio
    async def test_get_event_success(self, toolkit):
        result = await toolkit.get_event(url="http://test/calendars/tasks/event1.ics")
        assert result.summary == "Test Event"

    @pytest.mark.asyncio
    async def test_update_event_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.update_event(
            url="http://test/calendars/tasks/event1.ics",
            summary="Updated Event",
        )
        assert result.summary == "Updated Event"

    @pytest.mark.asyncio
    async def test_update_event_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.update_event(
                url="http://test/calendars/tasks/event1.ics",
                summary="Updated Event",
            )

    @pytest.mark.asyncio
    async def test_update_event_all_day(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.update_event(
            url="http://test/calendars/tasks/event1.ics",
            start=date(2024, 1, 1),
            end=date(2024, 1, 2),
            all_day=True,
        )
        assert result.all_day is True

    @pytest.mark.asyncio
    async def test_delete_event_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.delete_event(url="http://test/calendars/tasks/event1.ics")

    @pytest.mark.asyncio
    async def test_delete_event_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.delete_event(url="http://test/calendars/tasks/event1.ics")

    @pytest.mark.asyncio
    async def test_create_event_with_reminders(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
        reminders = [Reminder(minutes_before=15), Reminder(minutes_before=30)]
        result = await toolkit.create_event(
            calendar_url="http://test/calendars/tasks/",
            summary="Event with Reminder",
            start=start,
            end=end,
            reminders=reminders,
        )
        assert result.summary == "Event with Reminder"
        assert len(result.reminders) == 2

    @pytest.mark.asyncio
    async def test_create_event_with_single_reminder(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
        reminders = [Reminder(minutes_before=60)]
        result = await toolkit.create_event(
            calendar_url="http://test/calendars/tasks/",
            summary="Event with Single Reminder",
            start=start,
            end=end,
            reminders=reminders,
        )
        assert result.summary == "Event with Single Reminder"
        assert len(result.reminders) == 1
        assert result.reminders[0].minutes_before == 60

    @pytest.mark.asyncio
    async def test_update_event_with_reminders(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        reminders = [Reminder(minutes_before=15), Reminder(minutes_before=60)]
        result = await toolkit.update_event(
            url="http://test/calendars/tasks/event1.ics",
            summary="Updated Event with Reminders",
            reminders=reminders,
        )
        assert result.summary == "Updated Event with Reminders"
        assert len(result.reminders) == 2

    @pytest.mark.asyncio
    async def test_update_event_clear_reminders(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.update_event(
            url="http://test/calendars/tasks/event1.ics",
            summary="Updated Event without Reminders",
            reminders=[],
        )
        assert result.summary == "Updated Event without Reminders"
        assert len(result.reminders) == 0
