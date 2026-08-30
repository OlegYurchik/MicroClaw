import asyncio
from datetime import date, datetime, timedelta

from .dto import Calendar, Event, Reminder
from .settings import CalDAVSettings
from caldav.aio import AsyncCalendar, AsyncDAVClient, AsyncEvent, AsyncPrincipal
from caldav.elements import dav
from langgraph.types import interrupt
from loguru import logger
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from microclaw.dto import DecisionEnum
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
from microclaw.toolkits.settings import ToolKitSettings


class CalDAVToolKit(BaseToolKit[CalDAVSettings]):
    """Tools for managing calendars and events via CalDAV protocol."""

    required_capabilities: list[ToolKitCapability] = []
    write_capabilities: list[ToolKitCapability] = []
    discovery_capabilities: list[DiscoveryCapability] = []

    DATETIME_FORMAT = "%Y%m%dT%H%M%S"
    DATE_FORMAT = "%Y%m%d"

    _RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
        OSError,
    )

    def __init__(
        self, key: str, settings: ToolKitSettings, client: AsyncDAVClient | None = None
    ):
        super().__init__(key=key, settings=settings)
        self._client = client or AsyncDAVClient(
            url=self.arguments.url,
            username=self.arguments.username,
            password=self.arguments.password,
            ssl_verify_cert=self.arguments.verify_ssl,
        )
        self._principal = None

    @tool
    async def get_calendars(self) -> list[Calendar]:
        """
        Get all calendars accessible by the user.

        Returns:
            List of Calendar objects with url and name
        """
        principal = await self.get_principal()
        dav_calendars = await self._with_retry(principal.get_calendars)
        calendars = []
        for dav_calendar in dav_calendars:
            calendar = await self._convert_calendar_to_dto(calendar=dav_calendar)
            try:
                await self._get_calendar(calendar.url)
                calendars.append(calendar)
            except PermissionError:
                pass
        return calendars

    @tool
    async def create_calendar(self, name: str) -> Calendar:
        """
        Create a new calendar. Use this tool only when user explicitly requests calendar creation.

        Args:
            name: Calendar name

        Returns:
            Calendar object with url and name
        """

        if self.arguments.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.arguments.write_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Create calendar '{name}'?"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        principal = await self.get_principal()
        dav_calendar = await self._with_retry(
            principal.make_calendar,
            name=name,
            cal_id=None,
            supported_calendar_component_set=None,
        )
        calendar = await self._convert_calendar_to_dto(calendar=dav_calendar)

        return calendar

    @tool
    async def get_calendar(self, url: str) -> Calendar:
        """
        Get calendar by url. Use this tool only when user explicitly requests calendar details by
        URL.

        Args:
            url: Calendar full url (obtained from get_calendars or previous interactions)

        Returns:
            Calendar object with url and name
        """

        dav_calendar = AsyncCalendar(client=self._client, url=url)
        name = await self._with_retry(dav_calendar.get_property, dav.DisplayName())
        return Calendar(url=url, name=name or "")

    @tool
    async def delete_calendar(self, url: str) -> None:
        """
        Delete a calendar. Use this tool only when user explicitly requests calendar deletion.

        Args:
            url: Calendar full url (obtained from get_calendars or previous interactions)

        Returns:
            None - indicates successful operation
        """

        dav_calendar = await self._get_calendar(url)
        if self.arguments.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.arguments.write_mode is PermissionModeEnum.REQUEST:
            calendar_name = await self._with_retry(
                dav_calendar.get_property, dav.DisplayName()
            )
            confirmation_request_text = f"Delete calendar '{calendar_name}'?"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        await self._with_retry(dav_calendar.delete)

    @tool
    async def get_events(
        self,
        calendar_url: str | None = None,
        start: str | None = None,
        end: str | None = None,
        max_results: int = 20,
    ) -> list[Event]:
        """
        Get a list of events in a calendar or all calendars.
        When start and end dates are provided, recurring events are expanded—each
        occurrence within the range is returned as a separate event.

        Args:
            calendar_url: Full URL of the calendar (optional, all calendars if not specified)
            start: Start of the period in ISO 8601 format with timezone (optional)
            end: End of the period in ISO 8601 format with timezone (optional)
            max_results: Maximum number of results (optional, default: 20)

        Returns:
            List of Event objects
        """

        start_dt, end_dt = None, None
        if start is not None:
            start_dt = datetime.fromisoformat(start)
        if end is not None:
            end_dt = datetime.fromisoformat(end)

        if calendar_url is not None:
            dav_calendars = [await self._get_calendar(calendar_url)]
        else:
            principal = await self.get_principal()
            dav_calendars = await self._with_retry(principal.get_calendars)
            filtered_calendars = []
            for cal in dav_calendars:
                try:
                    await self._get_calendar(str(cal.url))
                    filtered_calendars.append(cal)
                except PermissionError:
                    pass
            dav_calendars = filtered_calendars

        events = []
        for dav_calendar in dav_calendars:
            if start_dt and end_dt:
                events_data = await self._with_retry(
                    dav_calendar.search,
                    start=start_dt,
                    end=end_dt,
                    event=True,
                    expand=True,
                )
            else:
                events_data = await self._with_retry(dav_calendar.get_events)

            for event in events_data[:max_results]:
                events.append(await self._convert_event_to_dto(event))

        return events

    @tool
    async def create_event(
        self,
        calendar_url: str,
        summary: str,
        start: datetime | date,
        end: datetime | date,
        description: str | None = None,
        location: str | None = None,
        all_day: bool = False,
        reminders: list[Reminder] | None = None,
    ) -> Event:
        """
        Create a new event. Use this tool only when user explicitly requests event creation.

        Args:
            calendar_url: Full URL of the calendar where the event will be created (obtained from get_calendars or previous interactions)
            summary: Event title/summary
            start: Event start datetime or date
            end: Event end datetime or date
            description: Event description (optional)
            location: Event location (optional)
            all_day: Whether this is an all-day event (optional, default: False)
            reminders: List of reminders with minutes_before (optional)

        Returns:
            Created Event object
        """

        dav_calendar = await self._get_calendar(calendar_url)
        if self.arguments.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.arguments.write_mode is PermissionModeEnum.REQUEST:
            calendar_name = await self._with_retry(
                dav_calendar.get_property, dav.DisplayName()
            )
            confirmation_request_text = (
                f"Create event '{summary}' in calendar '{calendar_name}'?\n"
                f"Start: {start}\n"
                f"End: {end}\n"
                f"All day: {all_day}"
            )
            if description is not None:
                confirmation_request_text += f"\nDescription: {description}"
            if location is not None:
                confirmation_request_text += f"\nLocation: {location}"
            if reminders:
                reminder_info = ", ".join(
                    [f"{r.minutes_before} min before" for r in reminders]
                )
                confirmation_request_text += f"\nReminders: {reminder_info}"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        if all_day:
            dtstart_line = f"DTSTART;VALUE=DATE:{start.strftime(self.DATE_FORMAT)}\n"
            dtend_line = f"DTEND;VALUE=DATE:{end.strftime(self.DATE_FORMAT)}\n"
        else:
            if isinstance(start, datetime):
                start_str = start.strftime(self.DATETIME_FORMAT)
            else:
                start_str = datetime.combine(start, datetime.min.time()).strftime(
                    self.DATETIME_FORMAT
                )
            if isinstance(end, datetime):
                end_str = end.strftime(self.DATETIME_FORMAT)
            else:
                end_str = datetime.combine(end, datetime.min.time()).strftime(
                    self.DATETIME_FORMAT
                )
            dtstart_line = f"DTSTART:{start_str}\n"
            dtend_line = f"DTEND:{end_str}\n"

        event_data = (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//MicroClaw//CalDAV Tool//EN\n"
            "BEGIN:VEVENT\n"
            f"SUMMARY:{summary}\n"
            f"{dtstart_line}"
            f"{dtend_line}"
        )
        if description:
            event_data += f"DESCRIPTION:{description}\n"
        if location:
            event_data += f"LOCATION:{location}\n"

        if reminders:
            for reminder in reminders:
                event_data += "BEGIN:VALARM\n"
                event_data += f"TRIGGER:-PT{reminder.minutes_before}M\n"
                event_data += "ACTION:DISPLAY\n"
                event_data += "DESCRIPTION:Reminder\n"
                event_data += "END:VALARM\n"

        event_data += "END:VEVENT\nEND:VCALENDAR\n"

        dav_event = await self._with_retry(dav_calendar.add_event, event_data)
        return await self._convert_event_to_dto(dav_event)

    @tool
    async def get_event(self, url: str) -> Event:
        """
        Get information about an event. Use this tool only when user explicitly requests event details.

        Args:
            url: Event full URL (obtained from get_events or previous interactions)

        Returns:
            Event object with full details
        """

        dav_event = AsyncEvent(client=self._client, url=url)
        await self._with_retry(dav_event.load)
        return await self._convert_event_to_dto(dav_event)

    @tool
    async def update_event(
        self,
        url: str,
        summary: str | None = None,
        start: datetime | date | None = None,
        end: datetime | date | None = None,
        description: str | None = None,
        location: str | None = None,
        all_day: bool | None = None,
        reminders: list[Reminder] | None = None,
    ) -> Event | None:
        """
        Update a calendar event. Use this tool only when user explicitly requests event update.

        Args:
            url: Event full URL (obtained from get_events or previous interactions)
            summary: New event title/summary (optional)
            start: New event start datetime or date (optional)
            end: New event end datetime or date (optional)
            description: New event description (optional)
            location: New event location (optional)
            all_day: Whether this is an all-day event (optional)
            reminders: New list of reminders (optional)

        Returns:
            Updated Event object if successful, None otherwise
        """

        dav_event = AsyncEvent(client=self._client, url=url)
        await self._with_retry(dav_event.load)

        if self.arguments.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.arguments.write_mode is PermissionModeEnum.REQUEST:
            event_data = await self._convert_event_to_dto(dav_event)
            changes = []
            if summary is not None:
                changes.append(f"summary: {summary}")
            if start is not None:
                changes.append(f"start: {start}")
            if end is not None:
                changes.append(f"end: {end}")
            if description is not None:
                changes.append(f"description: {description}")
            if location is not None:
                changes.append(f"location: {location}")
            if all_day is not None:
                changes.append(f"all_day: {all_day}")
            if reminders is not None:
                reminder_info = ", ".join(
                    [f"{r.minutes_before} min before" for r in reminders]
                )
                changes.append(f"reminders: {reminder_info}")

            changes_text = "\n".join(changes)
            confirmation_request_text = (
                f"Update event '{event_data.summary}'?\n{changes_text}"
            )
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        event_url_str = str(dav_event.url)
        calendar_url = event_url_str.rsplit("/", 1)[0]
        await self._get_calendar(calendar_url)

        event_instance = dav_event.icalendar_instance
        if not event_instance:
            return None
        for component in event_instance.subcomponents:
            if component.name != "VEVENT":
                continue
            if summary is not None:
                component["SUMMARY"] = summary
            if description is not None:
                component["DESCRIPTION"] = description
            if location is not None:
                component["LOCATION"] = location
            if start is not None:
                from icalendar import vDate, vDatetime

                if all_day:
                    start_date = vDate(start)
                    component["DTSTART"] = start_date
                else:
                    if isinstance(start, datetime):
                        start_dt = vDatetime(start)
                    else:
                        start_dt = vDatetime(
                            datetime.combine(start, datetime.min.time())
                        )
                    component["DTSTART"] = start_dt
            if end is not None:
                from icalendar import vDate, vDatetime

                if all_day:
                    end_date = vDate(end)
                    component["DTEND"] = end_date
                else:
                    if isinstance(end, datetime):
                        end_dt = vDatetime(end)
                    else:
                        end_dt = vDatetime(datetime.combine(end, datetime.min.time()))
                    component["DTEND"] = end_dt

            if reminders is not None:
                existing_alarms = [
                    sub for sub in component.subcomponents if sub.name == "VALARM"
                ]
                for alarm in existing_alarms:
                    component.subcomponents.remove(alarm)

                for reminder in reminders:
                    from icalendar import Alarm

                    alarm = Alarm()
                    alarm["TRIGGER"] = f"-PT{reminder.minutes_before}M"
                    alarm["ACTION"] = "DISPLAY"
                    alarm["DESCRIPTION"] = "Reminder"
                    component.add_component(alarm)

        dav_event.data = event_instance.to_ical()
        await self._with_retry(
            self._client.put,
            url,
            dav_event.data,
            {"Content-Type": "text/calendar; charset=utf-8"},
        )
        return await self._convert_event_to_dto(dav_event)

    @tool
    async def delete_event(self, url: str) -> None:
        """
        Delete a calendar event. Use this tool only when user explicitly requests event deletion.

        Args:
            url: Event full URL (obtained from get_events or previous interactions)

        Returns:
            None - indicates successful operation
        """

        calendar_url = url.rsplit("/", 1)[0]
        await self._get_calendar(calendar_url)
        if self.arguments.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.arguments.write_mode is PermissionModeEnum.REQUEST:
            dav_event = AsyncEvent(client=self._client, url=url)
            await self._with_retry(dav_event.load)
            event_data = await self._convert_event_to_dto(dav_event)
            confirmation_request_text = f"Delete event '{event_data.summary}'?"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        dav_event = AsyncEvent(client=self._client, url=url)
        await self._with_retry(dav_event.delete)

    async def _with_retry(self, func, *args, **kwargs):
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(self._RETRYABLE_EXCEPTIONS),
            reraise=True,
            before_sleep=before_sleep_log(logger, "warning"),
        ):
            with attempt:
                return await func(*args, **kwargs)

    async def get_principal(self) -> AsyncPrincipal:
        if self._principal is None:
            self._principal = await self._with_retry(self._client.get_principal)
        return self._principal

    async def _get_calendar(self, calendar_url: str) -> AsyncCalendar:
        dav_calendar = AsyncCalendar(client=self._client, url=calendar_url)
        if self.arguments.allowed_calendars is not None:
            calendar_name = await self._with_retry(
                dav_calendar.get_property, dav.DisplayName()
            )
            if calendar_name not in self.arguments.allowed_calendars:
                raise PermissionError(
                    f"Calendar '{calendar_name}' is not in allowed calendars list"
                )
        return dav_calendar

    async def _convert_calendar_to_dto(self, calendar: AsyncCalendar) -> Calendar:
        return Calendar(
            url=str(calendar.url),
            name=await self._with_retry(calendar.get_property, dav.DisplayName()),
        )

    async def _convert_event_to_dto(self, event: AsyncEvent) -> Event:
        event_instance = event.icalendar_instance
        if not event_instance:
            return Event(
                uid="",
                url=str(event.url),
                summary="",
                start=datetime.now(),
                end=datetime.now(),
            )

        for component in event_instance.walk():
            if component.name != "VEVENT":
                continue

            start = component["DTSTART"]
            end = component.get("DTEND")

            reminders: list[Reminder] = []
            for subcomponent in component.subcomponents:
                if subcomponent.name == "VALARM":
                    trigger = subcomponent.get("TRIGGER")
                    if trigger and trigger.dt:
                        if isinstance(trigger.dt, timedelta):
                            minutes_before = int(trigger.dt.total_seconds() / 60)
                            if minutes_before < 0:
                                minutes_before = abs(minutes_before)
                                reminders.append(
                                    Reminder(minutes_before=minutes_before)
                                )
                        elif isinstance(trigger.dt, str):
                            if trigger.dt.startswith("-PT") and trigger.dt.endswith(
                                "M"
                            ):
                                try:
                                    minutes_str = trigger.dt[3:-1]
                                    minutes = int(minutes_str)
                                    reminders.append(Reminder(minutes_before=minutes))
                                except (ValueError, IndexError):
                                    pass

            return Event(
                uid=str(component.get("UID", "")),
                url=str(event.url),
                summary=str(component.get("SUMMARY", "")),
                description=str(component.get("DESCRIPTION", "")),
                location=str(component.get("LOCATION", "")),
                start=start.dt,
                end=end.dt if end else None,
                all_day=not isinstance(start.dt, datetime),
                reminders=reminders,
            )

        return Event(
            uid="",
            url=event.url,
            summary="",
            start=datetime.now(),
            end=datetime.now(),
        )
