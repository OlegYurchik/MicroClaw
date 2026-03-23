import datetime

from pydantic import BaseModel, Field


class AddressBook(BaseModel):
    url: str = Field(description="URL of the address book")
    name: str = Field(description="Display name of the address book")


class Contact(BaseModel):
    uid: str = Field(description="Unique identifier of the contact")
    url: str | None = Field(default=None, description="URL link to the contact")
    display_name: str = Field(description="Display name of the contact")
    first_name: str | None = Field(default=None, description="First name of the contact")
    last_name: str | None = Field(default=None, description="Last name of the contact")
    email: str | None = Field(default=None, description="Email address of the contact")
    phone: str | None = Field(default=None, description="Phone number of the contact")
    organization: str | None = Field(default=None, description="Organization of the contact")
    title: str | None = Field(default=None, description="Title/position of the contact")
    note: str | None = Field(default=None, description="Note about the contact")
    birthday: datetime.date | None = Field(default=None, description="Birthday of the contact")
