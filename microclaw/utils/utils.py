from typing import Any, Callable


def get_by_key_or_first(storage: dict[str, Any], key: str | None = None) -> Any | None:
    if key is None and len(storage) > 0:
        return storage[next(iter(storage))]
    if key is None:
        key = "default"
    if key in storage:
        return storage[key]


def suppress_exception(exception_types: tuple[type[BaseException]] = (Exception,)) -> Callable:
    def decorator(function: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            try:
                return await function(*args, **kwargs)
            except exception_types:
                pass
        return wrapper
    return decorator
