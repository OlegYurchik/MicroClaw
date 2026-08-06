from textual.app import ComposeResult
from textual.containers import Horizontal

from .loader import ThinkingIndicator
from .stats import StatsWidget


class StatusBar(Horizontal):
    def compose(self) -> ComposeResult:
        self._thinking = ThinkingIndicator(id="thinking_indicator")
        self._stats = StatsWidget(id="stats_widget")
        yield self._thinking
        yield self._stats

    async def on_mount(self) -> None:
        self._thinking.display = False

    def show_thinking(self) -> None:
        self._thinking.display = True

    def hide_thinking(self) -> None:
        self._thinking.display = False

    def update_stats(
        self,
        usage: float | None = None,
        cost: float | None = None,
        currency: str = "$",
    ) -> None:
        self._stats.update_stats(usage=usage, cost=cost, currency=currency)
