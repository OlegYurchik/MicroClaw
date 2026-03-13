import enum
from typing import Any

from pydantic import BaseModel, Field, confloat

from microclaw.dto import Spending


class STTEngine(str, enum.Enum):
    OPENAI = "openai"
    YANDEX = "yandex"


class STTResult(BaseModel):
    text: str = Field(description="Recognized text")
    confidence: confloat(ge=0, le=1) | None = Field(
        default=None,
        description="Confidence score (0.0 to 1.0) if available",
    )
    language: str | None = Field(
        default=None,
        description="Detected language code (e.g., 'ru', 'en')",
    )
    spending: Spending | None = Field(
        default=None,
        description="Spending information for STT operation",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional engine-specific metadata",
    )
