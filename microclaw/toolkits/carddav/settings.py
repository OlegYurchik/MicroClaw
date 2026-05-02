from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class CardDAVSettings(BaseModel):
    """Settings for connecting to a CardDAV server."""
    
    url: str
    username: str
    password: str
    verify_ssl: bool = True
    default_address_book_path: str | None = None
    allowed_address_books: list[str] | None = None
    write_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
