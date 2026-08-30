import datetime
import string

import pytest

from microclaw.utils.utils import (
    get_by_key_or_first,
    random_string,
    suppress_exception,
    utcnow,
)


class TestGetByKeyOrFirst:
    def test_empty_storage_returns_none(self):
        result = get_by_key_or_first({})
        assert result is None

    def test_no_key_returns_first_element(self):
        storage = {"a": 1, "b": 2}
        result = get_by_key_or_first(storage)
        assert result == 1

    def test_with_key_returns_value(self):
        storage = {"a": 1, "b": 2}
        result = get_by_key_or_first(storage, key="b")
        assert result == 2

    def test_key_not_found_returns_none(self):
        storage = {"a": 1}
        result = get_by_key_or_first(storage, key="z")
        assert result is None


class TestSuppressException:
    @pytest.mark.asyncio
    async def test_catches_specified_exception(self):
        @suppress_exception((ValueError,))
        async def raises_value_error():
            raise ValueError("test")

        result = await raises_value_error()
        assert result is None

    @pytest.mark.asyncio
    async def test_reraises_other_exception(self):
        @suppress_exception((ValueError,))
        async def raises_type_error():
            raise TypeError("test")

        with pytest.raises(TypeError):
            await raises_type_error()

    @pytest.mark.asyncio
    async def test_returns_value_on_success(self):
        @suppress_exception()
        async def returns_value():
            return 42

        result = await returns_value()
        assert result == 42


class TestUtcnow:
    def test_returns_timezone_aware_datetime(self):
        result = utcnow()
        assert isinstance(result, datetime.datetime)
        assert result.tzinfo is not None

    def test_returns_utc_timezone(self):
        result = utcnow()
        assert result.utcoffset().total_seconds() == 0


class TestRandomString:
    def test_default_length(self):
        result = random_string()
        assert len(result) == 32

    def test_custom_length(self):
        result = random_string(length=10)
        assert len(result) == 10

    def test_custom_alphabet(self):
        result = random_string(length=100, alphabet="ab")
        assert set(result).issubset({"a", "b"})

    def test_default_alphabet_is_hexdigits(self):
        result = random_string(length=100)
        assert set(result).issubset(set(string.hexdigits))
