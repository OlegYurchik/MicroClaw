import enum
from pydantic import BaseModel, Field


class TLSModeEnum(str, enum.Enum):
    SSL = "ssl"
    STARTTLS = "starttls"
    NONE = "none"


class EmailSettings(BaseModel):
    imap_host: str = Field(
        description=(
            "IMAP server host (e.g., imap.gmail.com, imap.yandex.ru)"
        ),
    )
    imap_port: int = Field(
        default=993,
        description="IMAP server port (default: 993 for SSL)",
    )
    imap_tls_mode: TLSModeEnum = Field(
        default=TLSModeEnum.SSL,
        description="TLS mode: 'starttls' (587), 'ssl' (465), or 'none' (25)",
    )
    smtp_host: str = Field(
        description=(
            "SMTP server host (e.g., smtp.gmail.com, smtp.yandex.ru)"
        ),
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port (default: 587 for STARTTLS, 465 for SSL, 25 for plain)",
    )
    smtp_tls_mode: TLSModeEnum = Field(
        default=TLSModeEnum.SSL,
        description="TLS mode: 'starttls' (587), 'ssl' (465), or 'none' (25)",
    )
    username: str = Field(description="Email address for authentication")
    password: str = Field(description="Password or app password for authentication")
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificate (default: True)",
    )
    default_folder: str = Field(
        default="INBOX",
        description="Default folder to use (default: INBOX)",
    )
    sent_folder: str = Field(
        default="Sent",
        description="Folder to save sent messages (default: Sent)",
    )
