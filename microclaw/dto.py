from typing import Self

from pydantic import BaseModel


class Spending(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost: float = 0.0
    currency: str = "$"

    def __bool__(self) -> bool:
        return (
            self.input_tokens > 0 or
            self.output_tokens > 0 or
            self.cache_read_tokens > 0 or
            self.cache_write_tokens > 0 or
            self.cost > 0
        )

    def __add__(self, spending: Self):
        if self.currency != spending.currency:
            raise TypeError(
                "unsupported operand spendings with different currencies for +: "
                f"'{self.currency}' and '{spending.currency}'"
            )

        return Spending(
            input_tokens=self.input_tokens + spending.input_tokens,
            output_tokens=self.output_tokens + spending.output_tokens,
            cache_read_tokens=self.cache_read_tokens + spending.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + spending.cache_write_tokens,
            cost=self.cost + spending.cost,
            currency=self.currency,
        )

    def calculate_cost(self, model_costs: "ModelCosts"):
        self.cost = (
            self.input_tokens * model_costs.input / model_costs.per_tokens +
            self.output_tokens * model_costs.output / model_costs.per_tokens +
            self.cache_read_tokens * model_costs.cache_read / model_costs.per_tokens +
            self.cache_write_tokens * model_costs.cache_write / model_costs.per_tokens
        )

    def get_total_tokens(self) -> int:
        return (
            self.input_tokens +
            self.output_tokens +
            self.cache_read_tokens +
            self.cache_write_tokens
        )


class AgentMessage(BaseModel):
    role: str
    content: str
    chunked_message_id: str | None = None
    spending: Spending | None = None
    is_summary: bool = False  # Помечает, что это сообщение является суммаризацией диалога


class ChannelMessage(BaseModel):
    text: str
