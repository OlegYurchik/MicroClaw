from typing import Any
import datetime
import xml.etree.ElementTree as ET

import aiohttp
import vobject

from microclaw.toolkits import BaseToolKit, ToolKitSettings, tool
from .dto import AddressBook, Contact
from .settings import CardDAVSettings


class XMLBuilder:
    def addressbook_home_set(self) -> str:
        return (
            '<?xml version="1.0"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">'
            '<d:prop>'
            '<card:addressbook-home-set/>'
            '</d:prop>'
            '</d:propfind>'
        )

    def address_books_list(self) -> str:
        return (
            '<?xml version="1.0"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">'
            '<d:prop>'
            '<d:displayname/>'
            '<d:resourcetype/>'
            '</d:prop>'
            '</d:propfind>'
        )

    def address_book(self) -> str:
        return (
            '<?xml version="1.0"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">'
            '<d:prop>'
            '<d:displayname/>'
            '</d:prop>'
            '</d:propfind>'
        )

    def contacts_report(self) -> str:
        return (
            '<?xml version="1.0"?>'
            '<card:addressbook-query xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">'
            '<d:prop>'
            '<d:getetag/>'
            '<card:address-data/>'
            '</d:prop>'
            '</card:addressbook-query>'
        )

    def principal(self) -> str:
        return (
            '<?xml version="1.0"?>'
            '<d:propfind xmlns:d="DAV:">'
            '<d:prop>'
            '<d:current-user-principal/>'
            '</d:prop>'
            '</d:propfind>'
        )


class CardDAVToolKit(BaseToolKit[CardDAVSettings]):
    """Tools for managing address books and contacts via CardDAV protocol."""

    def __init__(self, key: str, settings: ToolKitSettings):
        super().__init__(key=key, settings=settings)

        self._principal_url: str | None = None
        self._xml = XMLBuilder()

    def _create_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            auth=(
                aiohttp.BasicAuth(self.settings.username, self.settings.password)
                if self.settings.username and self.settings.password
                else None
            ),
            headers={"Content-Type": "application/xml"},
            raise_for_status=True,
        )

    async def _get_principal_url(self) -> str:
        if self._principal_url:
            return self._principal_url

        async with self._create_session() as session:
            async with session.request(
                method="PROPFIND",
                url=self.settings.url,
                data=self._xml.principal(),
                headers={"Depth": "0"},
            ) as response:
                content = await response.text()

        if response.status == 207 and content:
            root = ET.fromstring(content)
            ns = {"d": "DAV:"}
            principal_elem = root.find(".//d:current-user-principal/d:href", ns)
            if principal_elem is not None:
                self._principal_url = self._get_full_url(principal_elem.text)
                return self._principal_url

        self._principal_url = self.settings.url.rstrip("/") + "/"
        return self._principal_url

    @tool
    async def get_address_books(self) -> list[AddressBook]:
        """
        Get all address books accessible by the user.

        Returns:
            List of AddressBook objects with url and name
        """

        address_books = []
        principal_url = await self._get_principal_url()
        
        async with self._create_session() as session:
            async with session.request(
                method="PROPFIND",
                url=principal_url,
                data=self._xml.addressbook_home_set(),
                headers={"Depth": "0"},
            ) as response:
                content = await response.text()

        if response.status != 207 or not content:
            return address_books

        address_book_url = self._parse_addressbook_home_set(content)
        if address_book_url is None:
            return address_books

        async with self._create_session() as session:
            async with session.request(
                method="PROPFIND",
                url=address_book_url,
                data=self._xml.address_books_list(),
                headers={"Depth": "1"},
            ) as response:
                content = await response.text()

        address_books = []
        if response.status == 207 and content:
            address_books = self._parse_address_books(content, address_book_url)

        return address_books

    @tool
    async def get_address_book(self, url: str) -> AddressBook:
        """
        Get address book by URL.

        Args:
            url: Address book full URL (obtained from get_address_books)

        Returns:
            AddressBook object with url and name
        """
        async with self._create_session() as session:
            async with session.request(
                method="PROPFIND",
                url=url,
                data=self._xml.address_book(),
                headers={"Depth": "0"},
            ) as response:
                content = await response.text()

        if response.status == 207 and content:
            display_name = self._parse_address_book(content)
            return AddressBook(url=url, name=display_name)

        return AddressBook(url=url, name="Address Book")

    @tool
    async def get_contacts(
            self,
            address_book_url: str | None = None,
            max_results: int = 50,
    ) -> list[Contact]:
        """
        Get a list of contacts from an address book or all address books.

        Args:
            address_book_url: Full URL of the address book (optional, all address books if not specified)
            max_results: Maximum number of results (optional, default: 50)

        Returns:
            List of Contact objects
        """
        if address_book_url is None:
            address_books = await self.get_address_books()
        else:
            address_books = [AddressBook(url=address_book_url, name="")]

        contacts = []
        async with self._create_session() as session:
            for address_book in address_books:
                async with session.request(
                    method="REPORT",
                    url=address_book.url,
                    data=self._xml.contacts_report(),
                    headers={"Depth": "1"},
                ) as response:
                    content = await response.text()

                if response.status == 207 and content:
                    parsed_contacts = self._parse_contacts(content, address_book.url)
                    contacts.extend(parsed_contacts)

                    if len(contacts) >= max_results:
                        break

        return contacts[:max_results]

    @tool
    async def get_contact(self, url: str) -> Contact | None:
        """
        Get contact by URL.

        Args:
            url: Contact full URL (obtained from get_contacts)

        Returns:
            Contact object with full details
        """
        async with self._create_session() as session:
            async with session.request(
                method="GET",
                url=url,
                headers={"Accept": "text/vcard"},
            ) as response:
                content = await response.text()

        if response.status == 200 and content:
            contact = await self._parse_vcard(content)
            contact.url = url
            return contact

    @tool
    async def create_contact(
            self,
            address_book_url: str,
            display_name: str,
            first_name: str | None = None,
            last_name: str | None = None,
            email: str | None = None,
            phone: str | None = None,
            organization: str | None = None,
            title: str | None = None,
            note: str | None = None,
            birthday: str | None = None,
    ) -> Contact:
        """
        Create a new contact. Use this tool only when user explicitly requests contact creation.

        Args:
            address_book_url: Full URL of the address book where the contact will be created
            display_name: Contact display name
            first_name: First name (optional)
            last_name: Last name (optional)
            email: Email address (optional)
            phone: Phone number (optional)
            organization: Organization (optional)
            title: Title/position (optional)
            note: Note about the contact (optional)
            birthday: Birthday of the contact (format: YYYY-MM-DD) (optional)

        Returns:
            Created Contact object
        """
        vcard_data = self._create_vcard_data(
            display_name=display_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            organization=organization,
            title=title,
            note=note,
            birthday=birthday,
        )

        async with self._create_session() as session:
            async with session.request(
                method="PUT",
                url=f"{address_book_url.rstrip('/')}/{display_name.replace(' ', '_')}.vcf",
                data=vcard_data,
                headers={"Content-Type": "text/vcard; charset=utf-8"},
            ) as response:
                await response.text()

        if response.status in (201, 204):
            contact = self._parse_vcard_sync(vcard_data)
            contact.url = f"{address_book_url.rstrip('/')}/{display_name.replace(' ', '_')}.vcf"
            return contact

    @tool
    async def update_contact(
            self,
            url: str,
            display_name: str | None = None,
            first_name: str | None = None,
            last_name: str | None = None,
            email: str | None = None,
            phone: str | None = None,
            organization: str | None = None,
            title: str | None = None,
            note: str | None = None,
            birthday: str | None = None,
    ) -> Contact | None:
        """
        Update a contact. Use this tool only when user explicitly requests contact update.

        Args:
            url: Contact full URL (obtained from get_contacts)
            display_name: New display name (optional)
            first_name: New first name (optional)
            last_name: New last name (optional)
            email: New email address (optional)
            phone: New phone number (optional)
            organization: New organization (optional)
            title: New title/position (optional)
            note: New note (optional)
            birthday: New birthday of the contact (format: YYYY-MM-DD) (optional)

        Returns:
            Updated Contact object if successful, None otherwise
        """
        async with self._create_session() as session:
            async with session.request(
                method="GET",
                url=url,
                headers={"Accept": "text/vcard"},
            ) as response:
                content = await response.text()

        if response.status != 200 or not content:
            return None

        vcard = vobject.readOne(content)

        self._update_vcard_fields(
            vcard=vcard,
            display_name=display_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            organization=organization,
            title=title,
            note=note,
            birthday=birthday,
        )

        vcard_data = vcard.serialize()

        async with self._create_session() as session:
            async with session.request(
                method="PUT",
                url=url,
                data=vcard_data,
                headers={"Content-Type": "text/vcard; charset=utf-8"},
            ) as response:
                pass

        if response.status in (200, 204):
            contact = await self._parse_vcard(vcard_data)
            contact.url = url
            return contact

    @tool
    async def delete_contact(self, url: str) -> None:
        """
        Delete a contact. Use this tool only when user explicitly requests contact deletion.

        Args:
            url: Contact full URL (obtained from get_contacts)
        """
        async with self._create_session() as session:
            async with session.request(method="DELETE", url=url):
                pass

    def _get_full_url(self, url: str) -> str:
        """Convert relative URL to full URL."""
        if url.startswith("http"):
            return url
        if url.startswith("/remote.php/"):
            return self.settings.url.split("/remote.php")[0] + url
        relative_url = url.lstrip("/")
        return f"{self.settings.url.rstrip('/')}/{relative_url}"

    def _create_vcard_data(
            self,
            display_name: str,
            first_name: str | None = None,
            last_name: str | None = None,
            email: str | None = None,
            phone: str | None = None,
            organization: str | None = None,
            title: str | None = None,
            note: str | None = None,
            birthday: str | None = None,
    ) -> str:
        """Create vCard data string from contact details."""
        vcard = vobject.vCard()
        vcard.add("fn").value = display_name

        if first_name or last_name:
            name = vcard.add("n")
            name.value = vobject.vcard.Name(
                family=last_name or "",
                given=first_name or "",
            )

        if email:
            vcard.add("email").value = email
        if phone:
            vcard.add("tel").value = phone
        if organization:
            vcard.add("org").value = [organization]
        if title:
            vcard.add("title").value = title
        if note:
            vcard.add("note").value = note
        if birthday:
            vcard.add("bday").value = birthday

        return vcard.serialize()

    def _update_vcard_fields(
            self,
            vcard: Any,
            display_name: str | None = None,
            first_name: str | None = None,
            last_name: str | None = None,
            email: str | None = None,
            phone: str | None = None,
            organization: str | None = None,
            title: str | None = None,
            note: str | None = None,
            birthday: str | None = None,
    ) -> None:
        """Update vCard fields with provided values."""
        if display_name:
            vcard.fn.value = display_name
        if first_name or last_name:
            self._update_vcard_name_field(vcard, first_name, last_name)
        if email:
            self._update_vcard_field(vcard, "email", email)
        if phone:
            self._update_vcard_field(vcard, "tel", phone)
        if organization:
            self._update_vcard_field(vcard, "org", [organization])
        if title:
            self._update_vcard_field(vcard, "title", title)
        if note:
            self._update_vcard_field(vcard, "note", note)
        if birthday:
            self._update_vcard_field(vcard, "bday", birthday)

    def _update_vcard_name_field(self, vcard: Any, first_name: str | None, last_name: str | None) -> None:
        if hasattr(vcard, "n") and vcard.n:
            vcard.n.value = vobject.vcard.Name(
                family=last_name or "",
                given=first_name or "",
            )
        else:
            name = vcard.add("n")
            name.value = vobject.vcard.Name(
                family=last_name or "",
                given=first_name or "",
            )

    def _update_vcard_field(self, vcard: Any, field_name: str, value: str | list[str]) -> None:
        if hasattr(vcard, field_name) and getattr(vcard, field_name):
            getattr(vcard, field_name).value = value
        else:
            vcard.add(field_name).value = value

    def _parse_addressbook_home_set(self, content: str) -> str | None:
        root = ET.fromstring(content)
        ns = {"d": "DAV:", "card": "urn:ietf:params:xml:ns:carddav"}

        href_elem = root.find(".//d:response/d:propstat/d:prop/card:addressbook-home-set/d:href", ns)
        if href_elem is not None:
            return self._get_full_url(href_elem.text)

    def _parse_responses(self, content: str, base_url: str, parser: callable) -> list:
        root = ET.fromstring(content)
        ns = {"d": "DAV:", "card": "urn:ietf:params:xml:ns:carddav"}

        results = []
        for response in root.findall(".//d:response", ns):
            result = parser(response, ns, base_url)
            if result:
                results.append(result)

        return results

    def _extract_address_book_from_response(
            self,
            response: Any,
            ns: dict[str, str],
            base_url: str,
    ) -> AddressBook | None:
        href_elem = response.find("d:href", ns)
        if href_elem is None:
            return None

        href = href_elem.text

        if href == base_url or href == base_url.rstrip("/") + "/":
            return None

        resourcetype_elem = response.find(".//d:propstat/d:prop/d:resourcetype/card:addressbook", ns)
        if resourcetype_elem is None:
            return None

        display_name_elem = response.find(".//d:propstat/d:prop/d:displayname", ns)
        display_name = display_name_elem.text if (display_name_elem is not None and display_name_elem.text) else "Address Book"
        return AddressBook(url=self._get_full_url(href), name=display_name)

    def _parse_address_books(self, content: str, base_url: str) -> list[AddressBook]:
        return self._parse_responses(content, base_url, self._extract_address_book_from_response)

    def _parse_address_book(self, content: str) -> str:
        root = ET.fromstring(content)
        ns = {"d": "DAV:"}
        display_name_elem = root.find(".//d:response/d:propstat/d:prop/d:displayname", ns)
        if display_name_elem is not None and display_name_elem.text:
            return display_name_elem.text
        return "Address Book"

    def _extract_contact_from_response(
        self, response: Any, ns: dict[str, str], base_url: str
    ) -> Contact | None:
        href_elem = response.find("d:href", ns)
        propstat = response.find("d:propstat", ns)

        if href_elem is None or propstat is None:
            return None

        href = href_elem.text
        address_data_elem = propstat.find(".//d:prop/card:address-data", ns)

        if address_data_elem is None or not address_data_elem.text:
            return None

        contact = self._parse_vcard_sync(address_data_elem.text)
        if href.startswith("http"):
            contact.url = href
        else:
            contact.url = self._get_full_url(href)
        return contact

    def _parse_contacts(self, content: str, base_url: str) -> list[Contact]:
        return self._parse_responses(content, base_url, self._extract_contact_from_response)

    def _parse_vcard_sync(self, vcard_data: str) -> Contact | None:
        vcard = vobject.readOne(vcard_data)
        return self._create_contact_from_vcard(vcard)

    async def _parse_vcard(self, vcard_data: str) -> Contact | None:
        vcard = vobject.readOne(vcard_data)
        return self._create_contact_from_vcard(vcard)

    def _create_contact_from_vcard(self, vcard: Any) -> Contact:
        birthday_str = self._get_vcard_value(vcard, "bday")
        birthday = None
        if birthday_str:
            try:
                birthday = datetime.datetime.strptime(birthday_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        return Contact(
            uid=self._get_vcard_value(vcard, "uid", ""),
            display_name=self._get_vcard_value(vcard, "fn", ""),
            first_name=self._get_name_part(vcard, first=True),
            last_name=self._get_name_part(vcard, first=False),
            email=self._get_vcard_value(vcard, "email"),
            phone=self._get_vcard_value(vcard, "tel"),
            organization=self._get_vcard_value(vcard, "org", list_value=True),
            title=self._get_vcard_value(vcard, "title"),
            note=self._get_vcard_value(vcard, "note"),
            birthday=birthday,
        )

    def _get_name_part(self, vcard: Any, first: bool = True) -> str | None:
        if hasattr(vcard, 'fn') and vcard.fn.value:
            parts = vcard.fn.value.split()
            return parts[0] if first and parts else (parts[-1] if parts else None)
        return None

    def _get_vcard_value(self, vcard: Any, field_name: str, default: Any = None, list_value: bool = False) -> Any:
        if hasattr(vcard, field_name) and getattr(vcard, field_name):
            value = getattr(vcard, field_name).value
            if list_value and value:
                return value[0] if value else None
            return value
        return default
