from pydantic import BaseModel


class DiscoveryInfo(BaseModel):
    name: str
    description: str | None = None
