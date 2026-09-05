from collections.abc import Callable
import datetime
import functools
import secrets
import string
from typing import Any


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def get_by_key_or_first(storage: dict[str, Any], key: str | None = None) -> Any | None:
    if key is None and len(storage) > 0:
        return storage[next(iter(storage))]
    if key is None:
        key = "default"
    if key in storage:
        return storage[key]


def suppress_exception(
    exception_types: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    def decorator(function: Callable) -> Callable:
        @functools.wraps(function)
        async def wrapper(*args, **kwargs):
            try:
                return await function(*args, **kwargs)
            except exception_types:
                pass

        return wrapper

    return decorator


def random_string(
    length: int = 32,
    alphabet: str = string.hexdigits,
) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(length))
