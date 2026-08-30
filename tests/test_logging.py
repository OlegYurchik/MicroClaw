import logging

from microclaw.logging import InterceptHandler, generate_formatter


class TestInterceptHandler:
    def test_emit_redirects_to_loguru(self, caplog):
        handler = InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        # Should not raise
        handler.emit(record)

    def test_emit_with_unknown_level(self, caplog):
        handler = InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=999,
            pathname="",
            lineno=0,
            msg="unknown",
            args=(),
            exc_info=None,
        )
        handler.emit(record)


class TestGenerateFormatter:
    def test_returns_callable(self):
        fmt = generate_formatter("{message}")
        assert callable(fmt)

    def test_formatter_with_extra(self):
        fmt = generate_formatter("{message}")
        result = fmt({"extra": {"key": "value"}})
        assert "key=value" in result

    def test_formatter_without_extra(self):
        fmt = generate_formatter("{message}")
        result = fmt({"extra": {}})
        assert result == "{message}{exception}\n"
