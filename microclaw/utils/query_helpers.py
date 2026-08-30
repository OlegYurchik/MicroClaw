from collections.abc import Callable
from typing import Any, TypeVar

from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import BasePagination


T = TypeVar("T")


def apply_pagination(items: list[T], pagination: BasePagination | None) -> list[T]:
    if pagination is None:
        return items
    offset = pagination.offset or 0
    limit = pagination.limit
    if limit is not None:
        return items[offset : offset + limit]
    return items[offset:]


def apply_sort(
    items: list[T],
    sort: BaseSort | None,
    key_map: dict[str, Callable[[T], Any]],
) -> list[T]:
    if sort is None or sort.sort_by is None:
        return items
    reverse = sort.sort_by_order == SortByOrder.desc
    key_func = key_map.get(sort.sort_by)
    if key_func is None:
        return items
    return sorted(items, key=key_func, reverse=reverse)
