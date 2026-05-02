from datetime import date, datetime

from caldav.aio import AsyncDAVClient, AsyncPrincipal, AsyncCalendar, AsyncEvent
from caldav.elements import dav

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
from microclaw.toolkits.settings import ToolKitSettings
from .dto import Calendar, Event
from .settings import CalDAVSettings


class CalDAVToolKit(BaseToolKit[CalDAVSettings]):
    """Tools for managing calendars and events via CalDAV protocol."""

    DATETIME_FORMAT = "%Y%m%dT%H%M%S"
    DATE_FORMAT = "%Y%m%d"

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

    async def _get_calendar(self, calendar_url: str) -> AsyncCalendar:
        dav_calendar = AsyncCalendar(client=self._client, url=calendar_url)
        if self.settings.allowed_calendars is not None:
            calendar_name = await dav_calendar.get_property(dav.DisplayName())
            if calendar_name not in self.settings.allowed_calendars:
                raise PermissionError(
                    f"Calendar '{calendar_name}' is not in allowed calendars list"
                )
        return dav_calendar

    @tool
    async def get_calendars(self) -> list[Calendar]:
        """
        Get all calendars accessible by the user.

        Returns:
            List of Calendar objects with url and name
        """

        principal = await self.get_principal()
        dav_calendars = await principal.get_calendars()
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

        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Create calendar '{name}'?"
            if not await self.request_confirmation(confirmation_request_text):
                raise UserDeniedAction()

        principal = await self.get_principal()
        dav_calendar = await principal.make_calendar(
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
        name = await dav_calendar.get_property(dav.DisplayName())
        return Calendar(url=url, name=name or "")

    @tool
    async def delete_calendar(self, url: str) -> None:
        """
        Delete a calendar. Use this tool only when user explicitly requests calendar deletion.

        Args:
            url: Calendar full url (obtained from get_calendars or previous interactions)
        
        Returns:
            None
        """

        dav_calendar = await self._get_calendar(url)
        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Delete calendar '{url}'?"
            if not await self.request_confirmation(confirmation_request_text):
                raise UserDeniedAction()

        await dav_calendar.delete()

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
            dav_calendars = await principal.get_calendars()
            # Filter by allowed calendars
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
                events_data = await dav_calendar.date_search(
                    start=start_dt,
                    end=end_dt,
                    expand=False,
                )
            else:
                events_data = await dav_calendar.get_events()

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
        
        Returns:
            Created Event object
        """

        dav_calendar = await self._get_calendar(calendar_url)
        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = (
                f"Create event '{summary}' in calendar '{calendar_url}'?\n"
                f"Start: {start}\n"
                f"End: {end}"
            )
            if not await self.request_confirmation(confirmation_request_text):
                raise UserDeniedAction()

        if all_day:
            dtstart_line = f"DTSTART;VALUE=DATE:{start.strftime(self.DATE_FORMAT)}\n"
            dtend_line = f"DTEND;VALUE=DATE:{end.strftime(self.DATE_FORMAT)}\n"
        else:
            if isinstance(start, datetime):
                start_str = start.strftime(self.DATETIME_FORMAT)
            else:
                start_str = datetime.combine(start, datetime.min.time()).strftime(self.DATETIME_FORMAT)
            if isinstance(end, datetime):
                end_str = end.strftime(self.DATETIME_FORMAT)
            else:
                end_str = datetime.combine(end, datetime.min.time()).strftime(self.DATETIME_FORMAT)
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
        event_data += (
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

        dav_event = await dav_calendar.add_event(event_data)
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
        await dav_event.load()
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
        
        Returns:
            Updated Event object if successful, None otherwise
        """

        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.settings.write_mode is PermissionModeEnum.REQUEST:
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

            changes_text = "\n".join(changes)
            confirmation_request_text = (
                f"Update event '{url}'?\n"
                f"{changes_text}"
            )
            if not await self.request_confirmation(confirmation_request_text):
                raise UserDeniedAction()

        dav_event = AsyncEvent(client=self._client, url=url)
        await dav_event.load()

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
                if all_day:
                    component["DTSTART"] = start.strftime(self.DATE_FORMAT)
                    component["DTSTART"].params = {"VALUE": "DATE"}
                else:
                    if isinstance(start, datetime):
                        component["DTSTART"] = start.strftime(self.DATETIME_FORMAT)
                    else:
                        component["DTSTART"] = datetime.combine(start, datetime.min.time()).strftime(self.DATETIME_FORMAT)
            if end is not None:
                if all_day:
                    component["DTEND"] = end.strftime(self.DATE_FORMAT)
                    component["DTEND"].params = {"VALUE": "DATE"}
                else:
                    if isinstance(end, datetime):
                        component["DTEND"] = end.strftime(self.DATETIME_FORMAT)
                    else:
                        component["DTEND"] = datetime.combine(end, datetime.min.time()).strftime(self.DATETIME_FORMAT)

        dav_event.data = event_instance.to_ical()
        await self._client.put(url, dav_event.data, {"Content-Type": "text/calendar; charset=utf-8"})
        return await self._convert_event_to_dto(dav_event)

    @tool
    async def delete_event(self, url: str) -> None:
        """
        Delete a calendar event. Use this tool only when user explicitly requests event deletion.
        
        Args:
            url: Event full URL (obtained from get_events or previous interactions)
        
        Returns:
            None
        """

        calendar_url = url.rsplit("/", 1)[0]
        await self._get_calendar(calendar_url)
        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations denied")
        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Delete event '{url}'?"
            if not await self.request_confirmation(confirmation_request_text):
                raise UserDeniedAction()

        dav_event = AsyncEvent(client=self._client, url=url)
        await dav_event.delete()

    async def _convert_calendar_to_dto(self, calendar: AsyncCalendar) -> Calendar:
        return Calendar(
            url=str(calendar.url),
            name=await calendar.get_property(dav.DisplayName()),
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

            return Event(
                uid=str(component.get("UID", "")),
                url=str(event.url),
                summary=str(component.get("SUMMARY", "")),
                description=str(component.get("DESCRIPTION", "")),
                location=str(component.get("LOCATION", "")),
                start=start.dt,
                end=end.dt if end else None,
                all_day=not isinstance(start.dt, datetime),
            )

        return Event(
            uid="",
            url=event.url,
            summary="",
            start=datetime.now(),
            end=datetime.now(),
        )
