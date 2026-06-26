from pydantic import BaseModel, Field


class VKToolKitSettings(BaseModel):
    token: str = Field(description="VK group token")
