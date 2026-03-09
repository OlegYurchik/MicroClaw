from pydantic import BaseModel, Field


class CardDAVSettings(BaseModel):
    """Settings for connecting to a CardDAV server."""
    
    url: str = Field(
        description=(
            "URL of the CardDAV server "
            "(e.g., https://carddav.example.com/carddav)"
        ),
    )
    username: str = Field(description="Username for authentication")
    password: str = Field(description="Password or app password for authentication")
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificate (default: True)",
    )
    default_address_book_path: str | None = Field(
        default=None,
        description="Path to the default address book (optional)",
    )
