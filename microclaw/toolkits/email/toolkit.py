import asyncio
import email
import re
import ssl
from contextlib import asynccontextmanager
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime, getaddresses
from typing import AsyncGenerator

from aioimaplib import aioimaplib
from aiosmtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.encoders import encode_base64

from microclaw.toolkits.base import BaseToolKit, tool
from .dto import EmailFolder, EmailMessage, EmailAttachment, FullEmailMessage
from .settings import EmailSettings, TLSModeEnum


# Monkey patching aioimaplib to support starttls
async def _protocol_starttls(self, host, ssl_context=None):
    if "STARTTLS" not in self.capabilities:
        aioimaplib.Abort("server does not have STARTTLS capability")
    if hasattr(self, "_tls_established") and self._tls_established:
        aioimaplib.Abort("TLS session already established")

    response = await self.execute(
        aioimaplib.Command("STARTTLS", self.new_tag(), loop=self.loop),
    )
    if response.result != "OK":
        return response

    if ssl_context is None:
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

    # Use loop.start_tls() to upgrade the transport to TLS
    # This is the modern way to do STARTTLS with asyncio
    new_transport = await self.loop.start_tls(
        self.transport,
        self,
        ssl_context,
        server_hostname=host,
    )
    self.transport = new_transport
    self._tls_established = True

    await self.capability()

    return response


async def _imap_starttls(self):
    return (await asyncio.wait_for(
        self.protocol.starttls(self.host), self.timeout))


aioimaplib.IMAP4ClientProtocol.starttls = _protocol_starttls
aioimaplib.IMAP4.starttls = _imap_starttls


class EmailToolKit(BaseToolKit[EmailSettings]):
    """Tools for managing emails via IMAP and SMTP protocols."""

    @asynccontextmanager
    async def _create_imap_client(self) -> AsyncGenerator:
        if self.settings.imap_tls_mode == TLSModeEnum.STARTTLS:
            client = aioimaplib.IMAP4(
                host=self.settings.imap_host,
                port=self.settings.imap_port,
                timeout=60,
            )
            await client.wait_hello_from_server()
            await client.starttls()
        else:
            client = aioimaplib.IMAP4_SSL(
                host=self.settings.imap_host,
                port=self.settings.imap_port,
                timeout=60,
            )
            if not self.settings.verify_ssl:
                client.cert_reqs = None
            await client.wait_hello_from_server()
        await client.login(
            self.settings.username,
            self.settings.password,
        )
        yield client

    @asynccontextmanager
    async def _create_smtp_client(self):
        client = SMTP(
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            use_tls=self.settings.smtp_tls_mode == TLSModeEnum.SSL,
            start_tls=self.settings.smtp_tls_mode == TLSModeEnum.STARTTLS,
            validate_certs=self.settings.verify_ssl,
        )
        await client.connect()
        await client.login(
            self.settings.username,
            self.settings.password,
        )
        yield client
        await client.quit()

    @tool
    async def get_folders(self) -> list[EmailFolder]:
        """
        Get list of all available email folders/mailboxes.

        Returns:
            List of EmailFolder objects with name, path, and flags
        """
        async with self._create_imap_client() as client:
            status, data = await client.list("", "*")
            if status != "OK":
                return []

            folders = []
            for line in data:
                if not line or not isinstance(line, bytes):
                    continue

                folder_str = line.decode("utf-8", errors="replace")
                match = re.search(r'"([^"]+)"$', folder_str)
                if match is None:
                    continue

                folder_name = match.group(1)
                folders.append(EmailFolder(
                    name=folder_name,
                    path=folder_name,
                    flags=[],
                ))

            return folders

    @tool
    async def get_messages(
            self,
            folder: str = "",
            limit: int = 5,
            unread_only: bool = False,
            since_date: str | None = None,
    ) -> list[EmailMessage]:
        """
        Get list of email messages from a folder.

        Args:
            folder: Folder name (default: default_folder from settings)
            limit: Maximum number of messages to return (default: 5)
            unread_only: If True, return only unread messages (default: False)
            since_date: Filter messages since this date (ISO format, optional)

        Returns:
            List of EmailMessage objects
        """
        folder = folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(folder)
            if status != "OK":
                return []

            criteria = "ALL"
            if unread_only:
                criteria = "UNSEEN"

            status, data = await client.search(criteria)
            if status != "OK":
                return []

            uid_data = data[0].split()
            if not uid_data:
                return []

            uid_list = uid_data[-limit:]

            messages = []
            for uid in reversed(uid_list):
                uid_str = uid.decode() if isinstance(uid, bytes) else uid
                status, msg_data = await client.fetch(uid_str, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue
                for part in msg_data:
                    if not isinstance(part, bytearray):
                        continue
                    raw_message = bytes(part)
                    msg = email.message_from_bytes(raw_message)
                    email_msg = self._parse_email_message(msg, uid_str, folder)
                    messages.append(email_msg)
                    break

            return messages

    @tool
    async def get_message_by_id(self, uid: str, folder: str = "") -> FullEmailMessage | None:
        """
        Get a specific email message by its UID.

        Args:
            uid: Message UID
            folder: Folder name (default: default_folder from settings)

        Returns:
            EmailMessage object or None if not found
        """
        folder = folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(folder)
            if status != "OK":
                return None

            status, message_parts = await client.fetch(uid, "(RFC822)")
            if status != "OK" or not message_parts:
                return None
            raw_message = b"".join(message_parts)
            message = email.message_from_bytes(raw_message)
            return self._parse_full_email_message(message=message, uid=uid, folder=folder)

    @tool
    async def search_messages(
            self,
            subject: str | None = None,
            from_addr: str | None = None,
            to_addr: str | None = None,
            body_text: str | None = None,
            folder: str = "",
            limit: int = 50,
    ) -> list[EmailMessage]:
        """
        Search for email messages matching criteria.

        Args:
            subject: Search in subject line
            from_addr: Search in sender address
            to_addr: Search in recipient address
            body_text: Search in message body
            folder: Folder name to search in (default: default_folder)
            limit: Maximum number of results (default: 50)

        Returns:
            List of matching EmailMessage objects
        """
        folder = folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(folder)
            if status != "OK":
                return []

            criteria_parts = []
            if subject:
                criteria_parts.append(f'SUBJECT "{subject}"')
            if from_addr:
                criteria_parts.append(f'FROM "{from_addr}"')
            if to_addr:
                criteria_parts.append(f'TO "{to_addr}"')
            if body_text:
                criteria_parts.append(f'BODY "{body_text}"')

            criteria = " ".join(criteria_parts) if criteria_parts else "ALL"

            status, data = await client.search(criteria)
            if status != "OK":
                return []

            uid_data = data[0].split()
            if not uid_data:
                return []

            uid_list = uid_data[-limit:]

            messages = []
            for uid in uid_list:
                status, msg_data = await client.fetch(uid, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue
                for part in msg_data:
                    if not isinstance(part, tuple):
                        continue
                    raw_message = part[1]
                    msg = email.message_from_bytes(raw_message)
                    email_msg = self._parse_email_message(msg, uid.decode(), folder)
                    messages.append(email_msg)

            return messages

    @tool
    async def delete_message(self, uid: str, folder: str = "") -> bool:
        """
        Delete an email message.

        Args:
            uid: Message UID to delete
            folder: Folder name (default: default_folder)

        Returns:
            True if deletion was successful
        """
        folder = folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(folder)
            if status != "OK":
                return False

            status, _ = await client.store(uid, "+FLAGS", r"(\Deleted)")
            if status != "OK":
                return False

            status, _ = await client.expunge()
            return status == "OK"

    @tool
    async def move_message(
            self,
            uid: str,
            destination_folder: str,
            source_folder: str = "",
    ) -> bool:
        """
        Move an email message to another folder.

        Args:
            uid: Message UID to move
            destination_folder: Target folder name
            source_folder: Source folder name (default: default_folder)

        Returns:
            True if move was successful
        """
        source_folder = source_folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(source_folder)
            if status != "OK":
                return False

            status, _ = await client.copy(uid, destination_folder)
            if status != "OK":
                return False

            status, _ = await client.store(uid, "+FLAGS", r"(\Deleted)")
            if status != "OK":
                return False

            status, _ = await client.expunge()
            return status == "OK"

    @tool
    async def mark_as_read(self, uid: str, folder: str = "") -> bool:
        """
        Mark an email message as read.

        Args:
            uid: Message UID
            folder: Folder name (default: default_folder)

        Returns:
            True if successful
        """
        folder = folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(folder)
            if status != "OK":
                return False

            status, _ = await client.store(uid, "+FLAGS", r"(\Seen)")
            return status == "OK"

    @tool
    async def mark_as_unread(self, uid: str, folder: str = "") -> bool:
        """
        Mark an email message as unread.

        Args:
            uid: Message UID
            folder: Folder name (default: default_folder)

        Returns:
            True if successful
        """
        folder = folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(folder)
            if status != "OK":
                return False

            status, _ = await client.store(uid, "-FLAGS", r"(\Seen)")
            return status == "OK"

    @tool
    async def send_email(
            self,
            to: str | list[str],
            subject: str,
            body_text: str = "",
            body_html: str = "",
            cc: str | list[str] | None = None,
            bcc: str | list[str] | None = None,
            attachments: list[str] | None = None,
    ) -> bool:
        """
        Send an email message.

        Args:
            to: Recipient email address(es)
            subject: Email subject
            body_text: Plain text body (optional)
            body_html: HTML body (optional)
            cc: CC recipient(s) (optional)
            bcc: BCC recipient(s) (optional)
            attachments: List of file paths to attach (optional)

        Returns:
            True if email was sent successfully
        """
        to_list = [to] if isinstance(to, str) else to
        cc_list = [cc] if isinstance(cc, str) else (cc or [])
        bcc_list = [bcc] if isinstance(bcc, str) else (bcc or [])

        msg = MIMEMultipart()
        msg["From"] = self.settings.username
        msg["To"] = ", ".join(to_list)
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate()

        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        elif body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

        if attachments:
            for filepath in attachments:
                with open(filepath, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{filepath.split("/")[-1]}"',
                    )
                    msg.attach(part)

        async with self._create_smtp_client() as client:
            recipients = to_list + cc_list + bcc_list
            await client.send_message(msg, recipients=recipients)

            try:
                async with self._create_imap_client() as imap_client:
                    msg_bytes = msg.as_bytes()
                    await imap_client.append(
                        self.settings.sent_folder,
                        r"(\Seen)",
                        None,
                        msg_bytes,
                    )
            except Exception:
                pass

    @tool
    async def get_unread_count(self, folder: str = "") -> int:
        """
        Get count of unread messages in a folder.

        Args:
            folder: Folder name (default: default_folder)

        Returns:
            Number of unread messages
        """
        folder = folder or self.settings.default_folder

        async with self._create_imap_client() as client:
            status, _ = await client.select(folder)
            if status != "OK":
                return 0

            status, data = await client.search("UNSEEN")
            if status != "OK":
                return 0

            uid_data = data[0].split()
            return len(uid_data) if uid_data else 0

    def _parse_full_email_message(self, message: Message, uid: str, folder: str) -> FullEmailMessage:
        email_message = self._parse_email_message(message=message, uid=uid, folder=folder)

        body_text = ""
        body_html = ""

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body_text = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    ) or ""
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    body_html = part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    ) or ""
        else:
            content_type = message.get_content_type()
            payload = message.get_payload(decode=True)
            if payload:
                decoded_payload = payload.decode(message.get_content_charset() or "utf-8", errors="replace")
                if content_type == "text/html":
                    body_html = decoded_payload
                else:
                    body_text = decoded_payload

        attachments = []
        for part in message.walk():
            filename = part.get_filename()
            if filename or "attachment" in str(part.get("Content-Disposition", "")):
                if filename:
                    filename = self._decode_header(filename)
                attachments.append(EmailAttachment(
                    filename=filename or "unnamed",
                    content_type=part.get_content_type() or "application/octet-stream",
                    size=len(part.get_payload(decode=True) or b""),
                    content_id=part.get("Content-ID", "").strip("<>"),
                ))

        return FullEmailMessage(
            **email_message.model_dump(),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )

    def _parse_email_message(self, message: Message, uid: str, folder: str) -> EmailMessage:
        message_id = message.get("Message-ID", "")
        subject = self._decode_header(message.get("Subject", ""))
        from_addr = self._decode_header(message.get("From", ""))

        to_list = self._extract_addresses(message.get("To", ""))
        cc_list = self._extract_addresses(message.get("Cc", ""))
        bcc_list = self._extract_addresses(message.get("Bcc", ""))

        date_str = message.get("Date", "")
        try:
            date = parsedate_to_datetime(date_str) if date_str else datetime.now()
        except (ValueError, TypeError):
            date = datetime.now()

        return EmailMessage(
            uid=uid,
            message_id=message_id,
            subject=subject,
            from_addr=from_addr,
            to=to_list,
            cc=cc_list,
            bcc=bcc_list,
            date=date,
            folder=folder,
            flags=[],
            raw_size=len(message.as_string()),
        )

    def _decode_header(self, header_value: str) -> str:
        if not header_value:
            return ""

        decoded = make_header(decode_header(header_value))
        return str(decoded)

    def _extract_addresses(self, address_str: str) -> list[str]:
        if not address_str:
            return []
        return [email for name, email in getaddresses([address_str])]
