from dataclasses import dataclass

from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination
import pytest

from microclaw.utils import apply_pagination, apply_sort


@dataclass
class Item:
    name: str
    value: int


@pytest.fixture
def items():
    return [
        Item("a", 1),
        Item("b", 3),
        Item("c", 2),
    ]


class TestApplyPagination:
    def test_none_pagination_returns_all(self, items):
        result = apply_pagination(items, None)
        assert result == items

    def test_offset_limit(self, items):
        pagination = OffsetPagination(offset=1, limit=1)
        result = apply_pagination(items, pagination)
        assert result == [items[1]]

    def test_offset_only(self, items):
        pagination = OffsetPagination(offset=1)
        result = apply_pagination(items, pagination)
        assert result == items[1:]

    def test_limit_one(self, items):
        pagination = OffsetPagination(offset=0, limit=1)
        result = apply_pagination(items, pagination)
        assert result == [items[0]]


class TestApplySort:
    def test_none_sort_returns_unchanged(self, items):
        result = apply_sort(items, None, {})
        assert result == items

    def test_sort_by_name_asc(self, items):
        sort = BaseSort(sort_by="name", sort_by_order=SortByOrder.asc)
        key_map = {"name": lambda x: x.name}
        result = apply_sort(items, sort, key_map)
        assert [i.name for i in result] == ["a", "b", "c"]

    def test_sort_by_value_desc(self, items):
        sort = BaseSort(sort_by="value", sort_by_order=SortByOrder.desc)
        key_map = {"value": lambda x: x.value}
        result = apply_sort(items, sort, key_map)
        assert [i.value for i in result] == [3, 2, 1]

    def test_unknown_key_returns_unchanged(self, items):
        sort = BaseSort(sort_by="unknown", sort_by_order=SortByOrder.asc)
        key_map = {"name": lambda x: x.name}
        result = apply_sort(items, sort, key_map)
        assert result == items

    def test_sort_by_none_returns_unchanged(self, items):
        sort = BaseSort(sort_by=None)
        key_map = {"name": lambda x: x.name}
        result = apply_sort(items, sort, key_map)
        assert result == items


class TestApplyPaginationEdgeCases:
    def test_zero_offset(self):
        items = [1, 2, 3]
        pagination = OffsetPagination(offset=0, limit=2)
        result = apply_pagination(items, pagination)
        assert result == [1, 2]

    def test_empty_list(self):
        items = []
        pagination = OffsetPagination(offset=0, limit=1)
        result = apply_pagination(items, pagination)
        assert result == []
