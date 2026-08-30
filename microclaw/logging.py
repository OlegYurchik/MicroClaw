from collections.abc import Callable
import logging

from loguru import logger


class InterceptHandler(logging.Handler):
    """Intercept standard library logging records and redirect them to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name  # type: ignore[arg-type]
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


class _LoguruFormatter:
    def __init__(self, base_format: str) -> None:
        self._base_format = base_format

    def __call__(self, record) -> str:
        fmt = self._base_format
        extra = record["extra"]
        if extra:
            extra_items = " | ".join(
                f"{k}={str(v).replace('{', '{{').replace('}', '}}')}"
                for k, v in extra.items()
            )
            fmt += f" | <yellow>{extra_items}</yellow>"
        return fmt + "{exception}\n"


def generate_formatter(base_format: str) -> Callable:
    return _LoguruFormatter(base_format)
