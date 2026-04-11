from pydantic import BaseModel

from microclaw.agents.settings import ModelSettings


class STTSettings(BaseModel):
    model: ModelSettings | str | None = None
    language: str = "ru"
