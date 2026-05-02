import enum
from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class TLSModeEnum(str, enum.Enum):
    SSL = "ssl"
    STARTTLS = "starttls"
    NONE = "none"


class EmailSettings(BaseModel):
    imap_host: str
    imap_port: int = 993
    imap_tls_mode: TLSModeEnum = TLSModeEnum.SSL
    smtp_host: str
    smtp_port: int = 587
    smtp_tls_mode: TLSModeEnum = TLSModeEnum.SSL
    username: str
    password: str
    verify_ssl: bool = True
    default_folder: str = "INBOX"
    sent_folder: str = "Sent"

    delete_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    send_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
