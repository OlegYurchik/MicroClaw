from pydantic import BaseModel, AnyHttpUrl


class A2AToolKitSettings(BaseModel):
    url: AnyHttpUrl
