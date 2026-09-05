import base64
import datetime

import pytest

from microclaw.agents.settings import ModelCosts
from microclaw.dto import AgentMessage, AgentMessageRoleEnum, Spending, Token


class TestSpending:
    def test_bool_empty(self):
        spending = Spending()
        assert not spending

    def test_bool_with_tokens(self):
        spending = Spending(input_tokens=1)
        assert spending

    def test_add_same_currency(self):
        a = Spending(input_tokens=1, output_tokens=2, cost=1.0, currency="$")
        b = Spending(input_tokens=3, output_tokens=4, cost=2.0, currency="$")
        result = a + b
        assert result.input_tokens == 4
        assert result.output_tokens == 6
        assert result.cost == 3.0
        assert result.currency == "$"

    def test_add_different_currency_raises(self):
        a = Spending(cost=1.0, currency="$")
        b = Spending(cost=2.0, currency="RUB")
        with pytest.raises(ValueError):
            _ = a + b

    def test_calculate_cost(self):
        spending = Spending(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=10,
            cache_write_tokens=5,
            audio_input_seconds=30,
            audio_output_seconds=15,
        )
        model_costs = ModelCosts(
            input=1.0,
            output=2.0,
            cache_read=0.5,
            cache_write=0.5,
            audio_input=0.1,
            audio_output=0.1,
        )
        spending.calculate_cost(model_costs)
        expected = (
            100 * 1.0 / 1_000_000
            + 50 * 2.0 / 1_000_000
            + 10 * 0.5 / 1_000_000
            + 5 * 0.5 / 1_000_000
            + 30 * 0.1 / 1
            + 15 * 0.1 / 1
        )
        assert spending.cost == pytest.approx(expected)

    def test_get_total_tokens(self):
        spending = Spending(
            input_tokens=1, output_tokens=2, cache_read_tokens=3, cache_write_tokens=4
        )
        assert spending.get_total_tokens() == 10


class TestAgentMessage:
    def test_validate_audio_bytes(self):
        msg = AgentMessage(role=AgentMessageRoleEnum.USER, audio=b"hello")
        assert msg.audio == b"hello"

    def test_validate_audio_base64(self):
        encoded = base64.b64encode(b"hello").decode("utf-8")
        msg = AgentMessage(role=AgentMessageRoleEnum.USER, audio=encoded)
        assert msg.audio == b"hello"

    def test_serialize_audio(self):
        msg = AgentMessage(role=AgentMessageRoleEnum.USER, audio=b"hello")
        data = msg.model_dump()
        assert data["audio"] == base64.b64encode(b"hello").decode("utf-8")

    def test_serialize_audio_none(self):
        msg = AgentMessage(role=AgentMessageRoleEnum.USER)
        data = msg.model_dump()
        assert data["audio"] is None


class TestToken:
    def test_is_valid_no_expiry(self):
        token = Token(token="test", user_id="12345678-1234-1234-1234-123456789012")
        assert token.is_valid() is True

    def test_is_valid_future_expiry(self):
        token = Token(
            token="test",
            user_id="12345678-1234-1234-1234-123456789012",
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=1),
        )
        assert token.is_valid() is True

    def test_is_valid_past_expiry(self):
        token = Token(
            token="test",
            user_id="12345678-1234-1234-1234-123456789012",
            expires_at=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=1),
        )
        assert token.is_valid() is False
