from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.carddav.toolkit import CardDAVToolKit
from microclaw.toolkits.enums import PermissionModeEnum


class TestCardDAVToolKit:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock(spec=aiohttp.ClientSession)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        def _make_response(status, text_content):
            resp = MagicMock()
            resp.status = status
            resp.text = AsyncMock(return_value=text_content)
            return resp

        # Principal response
        principal_response = _make_response(
            207,
            """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:propstat>
      <d:prop>
        <d:current-user-principal>
          <d:href>/principals/users/test/</d:href>
        </d:current-user-principal>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>""",
        )

        # Address book home set response
        home_set_response = _make_response(
            207,
            """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:propstat>
      <d:prop>
        <card:addressbook-home-set>
          <d:href>/addressbooks/</d:href>
        </card:addressbook-home-set>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>""",
        )

        # Address books list response
        books_response = _make_response(
            207,
            """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:href>/addressbooks/contacts/</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>Contacts</d:displayname>
        <d:resourcetype>
          <card:addressbook/>
        </d:resourcetype>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>""",
        )

        # Contacts report response
        contacts_response = _make_response(
            207,
            """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
  <d:response>
    <d:href>/addressbooks/contacts/john.vcf</d:href>
    <d:propstat>
      <d:prop>
        <card:address-data>BEGIN:VCARD\nVERSION:3.0\nFN:John Doe\nUID:123\nEND:VCARD</card:address-data>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>""",
        )

        # Contact GET response
        contact_response = _make_response(
            200, "BEGIN:VCARD\nVERSION:3.0\nFN:John Doe\nUID:123\nEND:VCARD"
        )

        # PUT response
        put_response = _make_response(201, "")

        # DELETE response
        delete_response = _make_response(204, "")

        # Address book propfind response
        book_response = _make_response(
            207,
            """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:propstat>
      <d:prop>
        <d:displayname>Contacts</d:displayname>
      </d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>""",
        )

        async def _request(method, url, **kwargs):
            data = kwargs.get("data") or ""
            if "current-user-principal" in data:
                return principal_response
            if "addressbook-home-set" in data:
                return home_set_response
            if "address_books_list" in data:
                return books_response
            if "addressbook-query" in data:
                return contacts_response
            if method == "GET" and ".vcf" in url:
                return contact_response
            if method == "PUT":
                return put_response
            if method == "DELETE":
                return delete_response
            if method == "PROPFIND" and "displayname" in data and "addressbooks" in url:
                return book_response
            return _make_response(404, "")

        session.request = AsyncMock(side_effect=_request)
        return session

    @pytest.fixture
    def toolkit(self, mock_session):
        settings = ToolKitSettings(
            path="microclaw.toolkits.carddav.toolkit.CardDAVToolKit",
            args={"url": "http://test", "username": "u", "password": "p"},
        )
        return CardDAVToolKit(key="carddav", settings=settings, session=mock_session)

    @pytest.mark.asyncio
    async def test_list_contacts_success(self, toolkit, mock_session):
        result = await toolkit.get_contacts(
            address_book_url="http://test/addressbooks/contacts/"
        )
        assert len(result) == 1
        assert result[0].display_name == "John Doe"

    @pytest.mark.asyncio
    async def test_get_contact_success(self, toolkit, mock_session):
        result = await toolkit.get_contact(
            url="http://test/addressbooks/contacts/john.vcf"
        )
        assert result is not None
        assert result.display_name == "John Doe"

    @pytest.mark.asyncio
    async def test_create_contact_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        result = await toolkit.create_contact(
            address_book_url="http://test/addressbooks/contacts/",
            display_name="Jane Doe",
        )
        assert result.display_name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_create_contact_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.create_contact(
                address_book_url="http://test/addressbooks/contacts/",
                display_name="Jane Doe",
            )

    @pytest.mark.asyncio
    async def test_delete_contact_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.delete_contact(url="http://test/addressbooks/contacts/john.vcf")
