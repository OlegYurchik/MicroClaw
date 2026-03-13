import base64
from typing import Self

from pydantic import BaseModel, field_serializer, field_validator


class Spending(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    audio_input_seconds: int = 0
    audio_output_seconds: int = 0
    cost: float = 0.0
    currency: str = "$"

    def __bool__(self) -> bool:
        return any((
            self.input_tokens,
            self.output_tokens,
            self.cache_read_tokens,
            self.cache_write_tokens,
            self.audio_input_seconds,
            self.audio_output_seconds,
            self.cost,
        ))

    def __add__(self, spending: Self):
        if self.currency != spending.currency:
            raise ValueError(
                f"Cannot sum spendings with different currencies: '{self.currency}' and "
                f"'{spending.currency}'"
            )

        return Spending(
            input_tokens=self.input_tokens + spending.input_tokens,
            output_tokens=self.output_tokens + spending.output_tokens,
            cache_read_tokens=self.cache_read_tokens + spending.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + spending.cache_write_tokens,
            audio_input_seconds=self.audio_input_seconds + spending.audio_input_seconds,
            audio_output_seconds=self.audio_output_seconds + spending.audio_output_seconds,
            cost=self.cost + spending.cost,
            currency=spending.currency,
        )

    def calculate_cost(self, model_costs: "ModelCosts"):
        self.cost = (
            self.input_tokens * model_costs.input / model_costs.per_tokens +
            self.output_tokens * model_costs.output / model_costs.per_tokens +
            self.cache_read_tokens * model_costs.cache_read / model_costs.per_tokens +
            self.cache_write_tokens * model_costs.cache_write / model_costs.per_tokens +
            self.audio_input_seconds * model_costs.audio_input / model_costs.per_audio_seconds +
            self.audio_output_seconds * model_costs.audio_output / model_costs.per_audio_seconds
        )

    def get_total_tokens(self) -> int:
        return sum((
            self.input_tokens,
            self.output_tokens,
            self.cache_read_tokens,
            self.cache_write_tokens,
        ))


class AgentMessage(BaseModel):
    role: str
    text: str | None = None
    chunked_message_id: str | None = None
    spending: Spending | None = None
    is_summary: bool = False
    audio: bytes | None = None
    audio_format: str | None = None

    @field_validator("audio", mode="before")
    @classmethod
    def validate_audio(cls, value: str | bytes | None) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        return base64.b64decode(value)

    @field_serializer("audio")
    def serialize_audio(self, value: bytes | None) -> str | None:
        if value is None:
            return None
        return base64.b64encode(value).decode("utf-8")


class ChannelMessage(BaseModel):
    text: str | None = None
    audio: bytes | None = None
    audio_format: str | None = None

    @field_validator("audio", mode="before")
    @classmethod
    def validate_audio(cls, value: str | bytes | None) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        return base64.b64decode(value)

    @field_serializer("audio")
    def serialize_audio(self, value: bytes | None) -> str | None:
        if value is None:
            return None
        return base64.b64encode(value).decode("utf-8")
