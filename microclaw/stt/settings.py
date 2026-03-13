from pydantic import BaseModel, Field

from microclaw.agents.settings import ModelSettings


class STTSettings(BaseModel):
    model: ModelSettings | str | None = None
    language: str = Field(default="ru", description="Language code for recognition (default: 'ru')")
