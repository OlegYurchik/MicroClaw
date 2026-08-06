from __future__ import annotations

from time import time

from textual.widget import Widget


class ThinkingIndicator(Widget):
    DEFAULT_CSS = """
    ThinkingIndicator {
        width: auto;
        height: auto;
        color: $text;
        text-style: dim;
    }
    """

    def __init__(
        self,
        label: str = "esc",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._label = label
        self._start_time = 0.0

    def _on_mount(self) -> None:
        self._start_time = time()
        self.auto_refresh = 1 / 8

    def render(self) -> str:
        if self.app is None or self.app.animation_level == "none":
            return f"{self._label}..."

        elapsed = time() - self._start_time
        speed = 1.2
        dot = "\u25cf"
        outline = "\u25cb"

        phases = [
            (elapsed * speed - dot_number / 3) % 1
            for dot_number in range(3)
        ]

        parts = []
        for phase in phases:
            if phase < 0.3:
                intensity = phase / 0.3
            elif phase < 0.7:
                intensity = 1.0
            else:
                intensity = max(0.0, 1.0 - (phase - 0.7) / 0.3)

            parts.append(dot if intensity >= 0.3 else outline)

        return f"{self._label} {' '.join(parts)}"
