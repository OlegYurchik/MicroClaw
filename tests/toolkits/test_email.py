from contextlib import asynccontextmanager

import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.email.toolkit import EmailToolKit


PLAIN_EMAIL = (
    b"From: sender@example.com\r\n"
    b"To: recipient@example.com\r\n"
    b"Subject: Test Subject\r\n"
    b"Date: Mon, 01 Jan 2024 00:00:00 +0000\r\n"
    b"Message-ID: <test123@example.com>\r\n"
    b"\r\n"
    b"Hello World"
)

MULTIPART_EMAIL = (
    b"From: sender@example.com\r\n"
    b"To: recipient@example.com\r\n"
    b"Subject: Multipart Test\r\n"
    b"Date: Mon, 01 Jan 2024 00:00:00 +0000\r\n"
    b"Message-ID: <multi@example.com>\r\n"
    b'Content-Type: multipart/mixed; boundary="boundary123"\r\n'
    b"\r\n"
    b"--boundary123\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n"
    b"\r\n"
    b"Plain text body\r\n"
    b"--boundary123\r\n"
    b"Content-Type: text/html; charset=utf-8\r\n"
    b"\r\n"
    b"<html><body>HTML body</body></html>\r\n"
    b"--boundary123\r\n"
    b"Content-Type: application/octet-stream\r\n"
    b'Content-Disposition: attachment; filename="test.txt"\r\n'
    b"\r\n"
    b"attachment content\r\n"
    b"--boundary123--\r\n"
)


class FakeIMAPClient:
    def __init__(self, email_bytes=None, empty_search=False):
        self._email_bytes = email_bytes or PLAIN_EMAIL
        self._empty_search = empty_search

    async def list(self, *args):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"']

    async def select(self, folder):
        return "OK", None

    async def uid(self, command, *args):
        if command == "SEARCH":
            if self._empty_search:
                return "OK", [b""]
            return "OK", [b"1 2"]
        if command == "FETCH":
            return "OK", [bytearray(self._email_bytes)]
        if command == "STORE":
            return "OK", None
        if command == "COPY":
            return "OK", None
        return "NO", None

    async def expunge(self):
        return "OK", None

    async def append(self, folder, flags, date, msg_bytes):
        return "OK", None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class FakeSMTPClient:
    async def send_message(self, msg, recipients=None):
        pass

    async def connect(self):
        pass

    async def login(self, user, password):
        pass

    async def quit(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@asynccontextmanager
async def fake_imap_factory(email_bytes=None, empty_search=False):
    yield FakeIMAPClient(email_bytes=email_bytes, empty_search=empty_search)


@asynccontextmanager
async def fake_smtp_factory():
    yield FakeSMTPClient()


def make_toolkit(imap_factory=None, smtp_factory=None):
    settings = ToolKitSettings(
        path="microclaw.toolkits.email.toolkit.EmailToolKit",
        args={
            "imap_host": "imap.example.com",
            "smtp_host": "smtp.example.com",
            "username": "user@example.com",
            "password": "secret",
        },
    )
    return EmailToolKit(
        key="email",
        settings=settings,
        imap_client_factory=imap_factory,
        smtp_client_factory=smtp_factory,
    )


@pytest.mark.asyncio
async def test_get_folders_success():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.get_folders()
    assert len(result) == 1
    assert result[0].name == "INBOX"


@pytest.mark.asyncio
async def test_get_messages_success():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.get_messages(folder="INBOX", limit=5)
    assert len(result) == 2
    assert result[0].subject == "Test Subject"
    assert result[0].from_addr == "sender@example.com"


@pytest.mark.asyncio
async def test_get_messages_empty_search():
    toolkit = make_toolkit(imap_factory=lambda: fake_imap_factory(empty_search=True))
    result = await toolkit.get_messages(folder="INBOX")
    assert result == []


@pytest.mark.asyncio
async def test_get_message_by_uid_success():
    toolkit = make_toolkit(
        imap_factory=lambda: fake_imap_factory(email_bytes=MULTIPART_EMAIL)
    )
    result = await toolkit.get_message_by_uid(uid="1", folder="INBOX")
    assert result is not None
    assert result.subject == "Multipart Test"
    assert result.body_text == "Plain text body"
    assert "HTML body" in result.body_html
    assert len(result.attachments) == 1
    assert result.attachments[0].filename == "test.txt"


@pytest.mark.asyncio
async def test_get_message_by_uid_not_found():
    class FailingIMAP(FakeIMAPClient):
        async def select(self, folder):
            return "NO", None

    @asynccontextmanager
    async def factory():
        yield FailingIMAP()

    toolkit = make_toolkit(imap_factory=factory)
    result = await toolkit.get_message_by_uid(uid="1", folder="INBOX")
    assert result is None


@pytest.mark.asyncio
async def test_search_messages_success():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.search_messages(subject="Test", folder="INBOX", limit=10)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_search_messages_no_criteria():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.search_messages(folder="INBOX")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_delete_messages_denied():
    from microclaw.toolkits.enums import PermissionModeEnum

    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    toolkit.arguments.delete_mode = PermissionModeEnum.DENY
    with pytest.raises(PermissionError):
        await toolkit.delete_messages(uids=["1"], folder="INBOX")


@pytest.mark.asyncio
async def test_move_message_success():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.move_message(
        uid="1", destination_folder="Archive", source_folder="INBOX"
    )
    assert result is True


@pytest.mark.asyncio
async def test_move_message_select_fails():
    class FailingIMAP(FakeIMAPClient):
        async def select(self, folder):
            return "NO", None

    @asynccontextmanager
    async def factory():
        yield FailingIMAP()

    toolkit = make_toolkit(imap_factory=factory)
    result = await toolkit.move_message(
        uid="1", destination_folder="Archive", source_folder="INBOX"
    )
    assert result is False


@pytest.mark.asyncio
async def test_mark_as_read_success():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.mark_as_read(uid="1", folder="INBOX")
    assert result is True


@pytest.mark.asyncio
async def test_mark_as_unread_success():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.mark_as_unread(uid="1", folder="INBOX")
    assert result is True


@pytest.mark.asyncio
async def test_send_email_denied():
    from microclaw.toolkits.enums import PermissionModeEnum

    toolkit = make_toolkit(smtp_factory=fake_smtp_factory)
    toolkit.arguments.send_mode = PermissionModeEnum.DENY
    with pytest.raises(PermissionError):
        await toolkit.send_email(to="to@example.com", subject="Test")


@pytest.mark.asyncio
async def test_send_email_success(tmp_path):
    from microclaw.toolkits.enums import PermissionModeEnum

    attachment = tmp_path / "file.txt"
    attachment.write_text("attachment data")

    toolkit = make_toolkit(smtp_factory=fake_smtp_factory)
    toolkit.arguments.send_mode = PermissionModeEnum.ALLOW
    result = await toolkit.send_email(
        to="to@example.com",
        subject="Test",
        body_text="Hello",
        attachments=[str(attachment)],
    )
    assert result is True


@pytest.mark.asyncio
async def test_get_unread_count_success():
    toolkit = make_toolkit(imap_factory=fake_imap_factory)
    result = await toolkit.get_unread_count(folder="INBOX")
    assert result == 2


@pytest.mark.asyncio
async def test_get_unread_count_select_fails():
    class FailingIMAP(FakeIMAPClient):
        async def select(self, folder):
            return "NO", None

    @asynccontextmanager
    async def factory():
        yield FailingIMAP()

    toolkit = make_toolkit(imap_factory=factory)
    result = await toolkit.get_unread_count(folder="INBOX")
    assert result == 0
