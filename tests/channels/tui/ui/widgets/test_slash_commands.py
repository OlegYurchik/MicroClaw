import datetime

from microclaw.channels.tui.ui.widgets.slash_commands import (
    format_time_ago,
)


class TestFormatTimeAgo:
    def test_just_now_for_future_date(self):
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=5
        )
        assert format_time_ago(future) == "just now"

    def test_seconds_ago(self):
        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            seconds=30
        )
        assert format_time_ago(dt) == "30s ago"

    def test_minutes_ago(self):
        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=5
        )
        assert format_time_ago(dt) == "5m ago"

    def test_one_minute_ago(self):
        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=1
        )
        assert format_time_ago(dt) == "1m ago"

    def test_hours_ago(self):
        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
        assert format_time_ago(dt) == "2h ago"

    def test_days_ago(self):
        dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)
        assert format_time_ago(dt) == "3d ago"
