from pydantic import BaseModel


class DiscogsToolKitSettings(BaseModel):
    personal_token: str
    timeout: int = 30
    retry: bool = False
