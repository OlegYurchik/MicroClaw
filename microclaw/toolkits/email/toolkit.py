import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
import email
from email.encoders import encode_base64
from email.header import decode_header, make_header
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import getaddresses, parsedate_to_datetime
import re
import ssl

from .dto import EmailAttachment, EmailFolder, EmailMessage, FullEmailMessage
from .settings import EmailSettings, TLSModeEnum
from aioimaplib import aioimaplib
from aiosmtplib import SMTP, SMTPException
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
    return await asyncio.wait_for(self.protocol.starttls(self.host), self.timeout)


aioimaplib.IMAP4ClientProtocol.starttls = _protocol_starttls
aioimaplib.IMAP4.starttls = _imap_starttls


class EmailToolKit(BaseToolKit[EmailSettings]):
    """Tools for managing emails via IMAP and SMTP protocols."""
    IMAP_TIMEOUT_SECONDS = 60
    required_capabilities: list[ToolKitCapability] = []
    write_capabilities: list[ToolKitCapability] = []
    discovery_capabilities: list[DiscoveryCapability] = []

    _RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
        OSError,
        aioimaplib.Error,
        SMTPException,
    )

    @tool
    async def get_folders(self) -> list[EmailFolder]:
        """
        Get list of all available email folders/mailboxes.

        Returns:
            List of EmailFolder objects with name, path, and flags
        """
        async with self._create_imap_client() as client:
            status, data = await self._with_retry(client.list, "", "*")
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
                folders.append(
                    EmailFolder(
                        name=folder_name,
                        path=folder_name,
                        flags=[],
                    )
                )

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
        Returns messages with their UIDs (real UIDs, not sequence numbers).

        Args:
            folder: Folder name (default: default_folder from settings)
            limit: Maximum number of messages to return (default: 5)
            unread_only: If True, return only unread messages (default: False)
            since_date: Filter messages since this date (ISO format, optional)

        Returns:
            List of EmailMessage objects
        """
        folder = folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, folder)
            if status != "OK":
                return []

            criteria = ["UNSEEN"] if unread_only else ["ALL"]

            uids = await self._get_uids_by_search(client, *criteria)
            if not uids:
                return []

            uid_list = uids[-limit:]

            messages = []
            for uid in reversed(uid_list):
                uid_str = uid.decode() if isinstance(uid, bytes) else uid
                status, message_parts = await self._with_retry(client.uid, "FETCH", uid_str, "(RFC822)")
                if status != "OK" or not message_parts:
                    continue
                raw_message = b""
                for part in message_parts:
                    if not isinstance(part, bytearray):
                        continue
                    raw_message = bytes(part)
                    msg = email.message_from_bytes(raw_message)
                    email_msg = self._parse_email_message(msg, uid_str, folder)
                    messages.append(email_msg)
                    break
            return messages

    @tool
    async def get_message_by_uid(
        self, uid: str, folder: str = ""
    ) -> FullEmailMessage | None:
        """
        Get a specific email message by its UID.

        Args:
            uid: Message UID
            folder: Folder name (default: default_folder from settings)

        Returns:
            EmailMessage object or None if not found
        """
        folder = folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, folder)
            if status != "OK":
                return None

            status, message_parts = await self._with_retry(client.uid, "FETCH", uid, "(RFC822)")
            if status != "OK" or not message_parts:
                return None

            raw_message = b""
            for part in message_parts:
                if not isinstance(part, bytearray):
                    continue
                raw_message = bytes(part)
                break
            if not raw_message:
                return None

            message = email.message_from_bytes(raw_message)
            return self._parse_full_email_message(
                message=message, uid=uid, folder=folder
            )

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
        folder = folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, folder)
            if status != "OK":
                return []

            criteria = []
            if subject:
                criteria.extend(["SUBJECT", f'"{subject}"'])
            if from_addr:
                criteria.extend(["FROM", f'"{from_addr}"'])
            if to_addr:
                criteria.extend(["TO", f'"{to_addr}"'])
            if body_text:
                criteria.extend(["BODY", f'"{body_text}"'])

            if not criteria:
                criteria = ["ALL"]

            uids = await self._get_uids_by_search(client, *criteria)
            if not uids:
                return []

            uid_list = uids[-limit:]

            messages = []
            for uid in uid_list:
                uid_str = uid.decode() if isinstance(uid, bytes) else uid
                status, message_parts = await self._with_retry(client.uid, "FETCH", uid_str, "(RFC822)")
                if status != "OK" or not message_parts:
                    continue
                raw_message = b""
                for part in message_parts:
                    if not isinstance(part, bytearray):
                        continue
                    raw_message = bytes(part)
                    msg = email.message_from_bytes(raw_message)
                    email_msg = self._parse_email_message(msg, uid_str, folder)
                    messages.append(email_msg)
                    break
                if not raw_message:
                    continue
                msg = email.message_from_bytes(raw_message)
                email_msg = self._parse_email_message(msg, uid_str, folder)
                messages.append(email_msg)

            return messages

    @tool
    async def delete_messages(self, uids: list[str], folder: str = "") -> None:
        """
        Delete an email messages by UIDs.

        The agent must verify that all messages were successfully deleted
        (e.g., by re-checking the folder or matching the number of removed messages).

        Args:
            uids: Messages UIDs to delete
            folder: Folder name (default: default_folder)

        Returns:
            True if deletion was successful
        """
        folder = folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, folder)
            if status != "OK":
                return None

            if self.arguments.delete_mode is PermissionModeEnum.DENY:
                raise PermissionError("Delete operations are disabled")
            if self.arguments.delete_mode is PermissionModeEnum.REQUEST:
                confirmation_messages = []
                for uid in uids:
                    summary = await self._fetch_message_summary(client, uid)
                    subject, from_addr = summary
                    confirmation_messages.append(
                        f"* {subject} (From: {from_addr})"
                    )
                confirmation_text = "\n".join(confirmation_messages)
                confirmation_request_text = (
                    f"Delete the following emails from {self.arguments.username}?\n"
                    f"{confirmation_text}"
                )
                decision = interrupt({"description": confirmation_request_text})
                if decision == DecisionEnum.REJECT.value:
                    raise UserDeniedAction()

            for uid in uids:
                status, _ = await self._with_retry(client.uid, "STORE", uid, "+FLAGS", r"(\Deleted)")
                if status != "OK":
                    return None

            status, _ = await self._with_retry(client.expunge)

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
        source_folder = source_folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, source_folder)
            if status != "OK":
                return False

            status, _ = await self._with_retry(client.uid, "COPY", uid, destination_folder)
            if status != "OK":
                return False

            status, _ = await self._with_retry(client.uid, "STORE", uid, "+FLAGS", r"(\Deleted)")
            if status != "OK":
                return False

            status, _ = await self._with_retry(client.expunge)
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
        folder = folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, folder)
            if status != "OK":
                return False

            status, _ = await self._with_retry(client.uid, "STORE", uid, "+FLAGS", r"(\Seen)")
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
        folder = folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, folder)
            if status != "OK":
                return False

            status, _ = await self._with_retry(client.uid, "STORE", uid, "-FLAGS", r"(\Seen)")
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
        if self.arguments.send_mode is PermissionModeEnum.DENY:
            raise PermissionError("Send operations are disabled")

        to_list = [to] if isinstance(to, str) else to
        cc_list = [cc] if isinstance(cc, str) else (cc or [])
        bcc_list = [bcc] if isinstance(bcc, str) else (bcc or [])

        msg = MIMEMultipart()
        msg["From"] = self.arguments.username
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

        if self.arguments.send_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = (
                f"Send message?\n\n📧 To: {', '.join(to_list)}\n"
            )
            if cc_list:
                confirmation_request_text += f"📋 CC: {', '.join(cc_list)}\n"
            if bcc_list:
                confirmation_request_text += f"🔒 BCC: {', '.join(bcc_list)}\n"
            confirmation_request_text += f"📝 Subject: {subject}\n"
            if attachments:
                confirmation_request_text += (
                    f"📎 Attachments: {', '.join(attachments)}\n"
                )
            confirmation_request_text += (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{(body_text or body_html)[:200]}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        async with self._create_smtp_client() as client:
            recipients = to_list + cc_list + bcc_list
            await self._with_retry(client.send_message, msg, recipients=recipients)

            try:
                async with self._create_imap_client() as imap_client:
                    msg_bytes = msg.as_bytes()
                    await self._with_retry(
                        imap_client.append,
                        self.arguments.sent_folder,
                        r"(\Seen)",
                        None,
                        msg_bytes,
                    )
            except Exception:
                pass

        return True

    @tool
    async def get_unread_count(self, folder: str = "") -> int:
        """
        Get count of unread messages in a folder.

        Args:
            folder: Folder name (default: default_folder)

        Returns:
            Number of unread messages
        """
        folder = folder or self.arguments.default_folder

        async with self._create_imap_client() as client:
            status, _ = await self._with_retry(client.select, folder)
            if status != "OK":
                return 0

            uids = await self._get_uids_by_search(client, "UNSEEN")
            return len(uids)

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

    async def _fetch_message_summary(
        self, client: aioimaplib.IMAP4, uid: str
    ) -> tuple[str, str]:

        status, message_parts = await self._with_retry(client.uid, "FETCH", uid, "(RFC822.HEADER)")
        if status == "OK" and message_parts:
            for part in message_parts:
                if isinstance(part, bytearray):
                    raw_header = bytes(part)
                    msg = email.message_from_bytes(raw_header)
                    subject = self._decode_header(msg.get("Subject", "unknown"))
                    from_addr = self._decode_header(msg.get("From", "unknown"))
                    return subject, from_addr
        raise RuntimeError(f"Failed to fetch message summary for UID {uid}")

    @asynccontextmanager
    async def _create_imap_client(self) -> AsyncGenerator:
        if self.arguments.imap_tls_mode == TLSModeEnum.STARTTLS:
            client = aioimaplib.IMAP4(
                host=self.arguments.imap_host,
                port=self.arguments.imap_port,
                timeout=self.IMAP_TIMEOUT_SECONDS,
            )
            await self._with_retry(client.wait_hello_from_server)
            await self._with_retry(client.starttls)
        else:
            client = aioimaplib.IMAP4_SSL(
                host=self.arguments.imap_host,
                port=self.arguments.imap_port,
                timeout=self.IMAP_TIMEOUT_SECONDS,
            )
            if not self.arguments.verify_ssl:
                client.cert_reqs = None
            await self._with_retry(client.wait_hello_from_server)
        await self._with_retry(
            client.login,
            self.arguments.username,
            self.arguments.password,
        )
        yield client

    async def _ensure_imap_authenticated(self, client: aioimaplib.IMAP4) -> None:
        status, _ = await self._with_retry(client.noop)
        if status == "OK":
            return
        if client.state == "NONAUTH":
            await self._with_retry(
                client.login,
                self.arguments.username,
                self.arguments.password,
            )

    @asynccontextmanager
    async def _create_smtp_client(self):
        client = SMTP(
            hostname=self.arguments.smtp_host,
            port=self.arguments.smtp_port,
            use_tls=self.arguments.smtp_tls_mode == TLSModeEnum.SSL,
            start_tls=self.arguments.smtp_tls_mode == TLSModeEnum.STARTTLS,
            validate_certs=self.arguments.verify_ssl,
        )
        await self._with_retry(client.connect)
        await self._with_retry(
            client.login,
            self.arguments.username,
            self.arguments.password,
        )
        yield client
        await client.quit()

    async def _get_uids_by_search(
        self, client: aioimaplib.IMAP4, *criteria: str
    ) -> list[str]:
        try:
            status, data = await self._with_retry(client.uid, "SEARCH", *criteria)
            if status == "OK" and data and data[0]:
                uid_line = data[0]
                if isinstance(uid_line, bytes):
                    uid_line = uid_line.decode()
                return uid_line.split()
            return []
        except (aioimaplib.Error, Exception):
            pass

        status, data = await self._with_retry(client.search, *criteria)
        if status != "OK" or not data or not data[0]:
            return []

        seq_line = data[0]
        if isinstance(seq_line, bytes):
            seq_line = seq_line.decode()
        seq_numbers = seq_line.split()
        if not seq_numbers:
            return []

        uids = []
        for seq in seq_numbers:
            status, fetch_data = await self._with_retry(client.fetch, seq, "(UID)")
            if status != "OK" or not fetch_data:
                continue
            uid = None
            for part in fetch_data:
                if isinstance(part, tuple) and len(part) == 2:
                    if part[0].upper() == b"UID":
                        uid = part[1].decode()
                        break
                elif isinstance(part, bytes):
                    match = re.search(rb"UID (\d+)", part)
                    if match:
                        uid = match.group(1).decode()
                        break
            if uid:
                uids.append(uid)
        return uids

    def _parse_full_email_message(
        self, message: Message, uid: str, folder: str
    ) -> FullEmailMessage:
        email_message = self._parse_email_message(
            message=message, uid=uid, folder=folder
        )

        body_text = ""
        body_html = ""

        if message.is_multipart():
            for part in message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if (
                    content_type == "text/plain"
                    and "attachment" not in content_disposition
                ):
                    body_text = (
                        part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                        or ""
                    )
                elif (
                    content_type == "text/html"
                    and "attachment" not in content_disposition
                ):
                    body_html = (
                        part.get_payload(decode=True).decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                        or ""
                    )
        else:
            content_type = message.get_content_type()
            payload = message.get_payload(decode=True)
            if payload:
                decoded_payload = payload.decode(
                    message.get_content_charset() or "utf-8", errors="replace"
                )
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
                attachments.append(
                    EmailAttachment(
                        filename=filename or "unnamed",
                        content_type=part.get_content_type()
                        or "application/octet-stream",
                        size=len(part.get_payload(decode=True) or b""),
                        content_id=part.get("Content-ID", "").strip("<>"),
                    )
                )

        return FullEmailMessage(
            **email_message.model_dump(),
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
        )

    def _parse_email_message(
        self, message: Message, uid: str, folder: str
    ) -> EmailMessage:
        message_id = message.get("Message-ID", "")
        subject = self._decode_header(message.get("Subject"))
        from_addr = self._decode_header(message.get("From"))

        to_list = self._extract_addresses(message.get("To"))
        cc_list = self._extract_addresses(message.get("Cc"))
        bcc_list = self._extract_addresses(message.get("Bcc"))

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

        return [email for name, email in getaddresses([address_str]) if email]
