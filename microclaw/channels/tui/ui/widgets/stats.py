from textual.widgets import Static


class StatsWidget(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._context_usage = None
        self._cost = None
        self._currency = "$"

    def update_stats(
        self,
        usage: float | None = None,
        cost: float | None = None,
        currency: str = "$",
    ) -> None:
        self._context_usage = usage
        self._cost = cost
        self._currency = currency

        parts = []
        if self._context_usage is not None:
            parts.append(f"[dim]{self._context_usage:.2f}% context[/dim]")
        if self._cost is not None:
            parts.append(f"[dim]{self._cost:.4f} {self._currency}[/dim]")

        text = " · ".join(parts)
        self.update(text)
