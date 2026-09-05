from unittest.mock import MagicMock

from caldav.async_davclient import AsyncDAVClient as _AsyncDAVClient
from caldav.collection import Calendar, Principal
from caldav.davclient import URL, DAVResponse
from caldav.protocol.xml_parsers import (  # type: ignore[reportPrivateUsage]  # internal API; pinned in pyproject.toml
    _parse_calendar_query_response,
    _parse_propfind_response,
)


class _AsyncDAVClientType(type(_AsyncDAVClient)):
    @property
    def __name__(cls):
        return "AsyncDAVClient"


class FakeAsyncDAVClient(_AsyncDAVClient, metaclass=_AsyncDAVClientType):
    """Test double for caldav AsyncDAVClient.

    Inherits from AsyncDAVClient so ``isinstance(client, AsyncDAVClient)``
    returns ``True``, which is required by caldav's dual-mode async logic.
    """



    def __init__(self, url: str = "http://test") -> None:
        # bypass httpx session creation in AsyncDAVClient.__init__
        self.url = URL.objectify(url)
        self.features = MagicMock()
        self.features.is_supported = MagicMock(return_value={"support": "full"})
        self.huge_tree = False
        self.headers: dict[str, str] = {}

    def _create_session(self) -> None:
        pass

    async def close(self) -> None:
        pass

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _resp(status: int, xml: bytes, parse: str | None = None) -> DAVResponse:
        fake_response = MagicMock()
        fake_response.status_code = status
        fake_response.headers = {"Content-Type": "text/xml; charset=utf-8"}
        fake_response.content = xml
        fake_response.text = xml.decode("utf-8", errors="replace")
        fake_response.reason = "OK"
        resp = DAVResponse(response=fake_response, davclient=None)
        if parse == "propfind":
            resp.results = _parse_propfind_response(xml, status, huge_tree=False)
        elif parse == "calendar_query":
            resp.results = _parse_calendar_query_response(xml, status, huge_tree=False)
        return resp

    _PRINCIPAL_XML = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/principals/users/test/</d:href>
    <d:propstat>
      <d:prop>
        <d:current-user-principal><d:href>/principals/users/test/</d:href></d:current-user-principal>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    _HOME_SET_XML = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/principals/users/test/</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-home-set><d:href>/calendars/</d:href></cal:calendar-home-set>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    _CALENDAR_LIST_XML = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendars/tasks/</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>My Tasks</d:displayname>
        <d:resourcetype><cal:calendar/></d:resourcetype>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    _DISPLAYNAME_XML = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/calendars/tasks/</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>My Tasks</d:displayname>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    _TODO_REPORT_XML = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendars/tasks/todo1.ics</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VTODO
UID:todo-1
SUMMARY:Test Task
END:VTODO
END:VCALENDAR</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    _EVENT_REPORT_XML = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendars/tasks/event1.ics</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:event-1
SUMMARY:Test Event
DTSTART:20240101T100000Z
DTEND:20240101T110000Z
END:VEVENT
END:VCALENDAR</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    _EVENT_WITH_REMINDERS_REPORT_XML = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendars/tasks/event2.ics</d:href>
    <d:propstat>
      <d:prop>
        <cal:calendar-data>BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:event-2
SUMMARY:Event with Reminders
DTSTART:20240101T100000Z
DTEND:20240101T110000Z
BEGIN:VALARM
TRIGGER:-PT15M
ACTION:DISPLAY
DESCRIPTION:Reminder
END:VALARM
BEGIN:VALARM
TRIGGER:-PT60M
ACTION:DISPLAY
DESCRIPTION:Reminder
END:VALARM
END:VEVENT
END:VCALENDAR</cal:calendar-data>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    _EMPTY_CALENDAR_DATA = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VTODO\nUID:todo-1\n"
        b"SUMMARY:Test Task\nEND:VTODO\nEND:VCALENDAR"
    )

    _EMPTY_EVENT_DATA = (
        b"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:event-1\n"
        b"SUMMARY:Test Event\nDTSTART:20240101T100000Z\n"
        b"DTEND:20240101T110000Z\nEND:VEVENT\nEND:VCALENDAR"
    )

    # ------------------------------------------------------------------
    # HTTP wrappers
    # ------------------------------------------------------------------
    async def request(
        self,
        url: str,
        method: str = "GET",
        body: str = "",
        headers: dict[str, str] | None = None,
    ) -> DAVResponse:
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.status = 200
        fake_response.headers = {}
        fake_response.reason = "OK"
        if "event2" in url:
            event_data = (
                b"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:event-2\n"
                b"SUMMARY:Event with Reminders\nDTSTART:20240101T100000Z\n"
                b"DTEND:20240101T110000Z\nBEGIN:VALARM\nTRIGGER:-PT15M\n"
                b"ACTION:DISPLAY\nDESCRIPTION:Reminder\nEND:VALARM\nBEGIN:VALARM\n"
                b"TRIGGER:-PT60M\nACTION:DISPLAY\nDESCRIPTION:Reminder\nEND:VALARM\n"
                b"END:VEVENT\nEND:VCALENDAR"
            )
            fake_response.content = event_data
            fake_response.text = event_data.decode("utf-8")
        elif "event" in url:
            fake_response.content = self._EMPTY_EVENT_DATA
            fake_response.text = self._EMPTY_EVENT_DATA.decode("utf-8")
        else:
            fake_response.content = self._EMPTY_CALENDAR_DATA
            fake_response.text = self._EMPTY_CALENDAR_DATA.decode("utf-8")
        fake_response.raw = fake_response.content
        return DAVResponse(response=fake_response, davclient=None)

    def _parse_icalendar_from_body(self, body: str) -> bytes:
        """Extract and return iCalendar data for events with reminders."""
        body_str = body.decode("utf-8") if isinstance(body, bytes) else body
        if "BEGIN:VEVENT" in body_str and "BEGIN:VALARM" in body_str:
            simple_event = (
                b"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:event-2\n"
                b"SUMMARY:Event with Reminders\nDTSTART:20240101T100000Z\n"
                b"DTEND:20240101T110000Z\nBEGIN:VALARM\nTRIGGER:-PT15M\n"
                b"ACTION:DISPLAY\nDESCRIPTION:Reminder\nEND:VALARM\nBEGIN:VALARM\n"
                b"TRIGGER:-PT60M\nACTION:DISPLAY\nDESCRIPTION:Reminder\nEND:VALARM\n"
                b"END:VEVENT\nEND:VCALENDAR"
            )
            return simple_event
        return self._EMPTY_EVENT_DATA

    async def propfind(
        self,
        url: str | None = None,
        body: str = "",
        depth: int = 0,
        headers: dict[str, str] | None = None,
        props: list[str] | None = None,
    ) -> DAVResponse:
        body_str = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        if props and any("current-user-principal" in p for p in props):
            return self._resp(207, self._PRINCIPAL_XML, parse="propfind")
        if "calendar-home-set" in body_str:
            return self._resp(207, self._HOME_SET_XML, parse="propfind")
        if "resourcetype" in body_str:
            return self._resp(207, self._CALENDAR_LIST_XML, parse="propfind")
        if "displayname" in body_str.lower():
            return self._resp(207, self._DISPLAYNAME_XML, parse="propfind")
        return self._resp(404, b"")

    async def report(
        self,
        url: str | None = None,
        body: str = "",
        depth: int | None = 0,
        headers: dict[str, str] | None = None,
    ) -> DAVResponse:
        body_str = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        if "VEVENT" in body_str:
            return self._resp(207, self._EVENT_REPORT_XML, parse="calendar_query")
        return self._resp(207, self._TODO_REPORT_XML, parse="calendar_query")

    async def put(
        self,
        url: str,
        body: str,
        headers: dict[str, str] | None = None,
    ) -> DAVResponse:
        fake_response = MagicMock()
        fake_response.status_code = 201
        fake_response.status = 201
        fake_response.headers = {}
        fake_response.reason = "Created"
        if "event" in url:
            content = self._parse_icalendar_from_body(body)
        else:
            content = b""
        fake_response.content = content
        fake_response.text = content.decode("utf-8") if content else ""
        fake_response.raw = fake_response.content
        return DAVResponse(response=fake_response, davclient=None)

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> DAVResponse:
        return self._resp(204, b"")

    async def mkcalendar(
        self,
        url: str,
        body: str = "",
        headers: dict[str, str] | None = None,
    ) -> DAVResponse:
        return self._resp(201, b"")

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------
    async def get_principal(self) -> Principal:
        return Principal(client=self, url="http://test/principals/users/test/")

    async def get_calendars(self, principal: Principal | None = None) -> list[Calendar]:
        return [
            Calendar(client=self, url="http://test/calendars/tasks/", name="My Tasks")
        ]
