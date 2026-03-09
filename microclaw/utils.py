from typing import Any


def get_by_key_or_first(storage: dict[str, Any], key: str | None = None) -> Any | None:
    if key is None and len(storage) > 0:
        return storage[next(iter(storage))]
    if key is None:
        key = "default"
    if key in storage:
        return storage[key]
