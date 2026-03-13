from datetime import datetime
from pydantic import BaseModel, Field


class EmailFolder(BaseModel):
    name: str = Field(description="Folder name (e.g., INBOX, Sent, Drafts)")
    path: str = Field(description="Full folder path")
    flags: list[str] = Field(default_factory=list, description="Folder flags (e.g., \\HasNoChildren)")


class EmailAttachment(BaseModel):
    filename: str = Field(description="Attachment filename")
    content_type: str = Field(description="MIME type of the attachment")
    size: int = Field(description="Attachment size in bytes")
    content_id: str | None = Field(default=None, description="Content-ID for inline attachments")


class EmailMessage(BaseModel):
    uid: str = Field(description="Unique identifier of the message in the mailbox")
    message_id: str = Field(description="Message-ID header value")
    subject: str = Field(description="Email subject")
    from_addr: str = Field(description="Sender email address")
    to: list[str] = Field(default_factory=list, description="List of recipient email addresses")
    cc: list[str] = Field(default_factory=list, description="List of CC email addresses")
    bcc: list[str] = Field(default_factory=list, description="List of BCC email addresses")
    date: datetime = Field(description="Date the email was sent")
    folder: str = Field(description="Folder where the message is stored")
    flags: list[str] = Field(default_factory=list, description="Message flags (e.g., \\Seen, \\Flagged)")
    raw_size: int = Field(description="Message size in bytes")


class FullEmailMessage(EmailMessage):
    body_text: str = Field(default="", description="Plain text body content")
    body_html: str = Field(default="", description="HTML body content")
    attachments: list[EmailAttachment] = Field(default_factory=list, description="List of attachments")
