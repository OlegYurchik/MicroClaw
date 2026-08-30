import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.service import MicroclawService
from microclaw.settings import MicroclawSettings


@pytest.fixture
def mock_resolver():
    resolver = MagicMock()
    channel = MagicMock()
    cron = MagicMock()
    resolver.resolve_channels = AsyncMock(return_value={"telegram": channel})
    resolver.resolve_crons = AsyncMock(return_value={"flush": cron})
    return resolver, channel, cron


@pytest.mark.asyncio
async def test_run_resolves_channels_and_crons(mock_resolver):
    resolver, channel, cron = mock_resolver
    settings = MicroclawSettings()
    service = MicroclawService(settings=settings, resolver=resolver)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(service.run(), timeout=0.01)

    resolver.resolve_channels.assert_awaited_once()
    resolver.resolve_crons.assert_awaited_once()


def test_dependencies_before_run_raises():
    settings = MicroclawSettings()
    service = MicroclawService(settings=settings, resolver=MagicMock())

    with pytest.raises(RuntimeError, match="Dependencies accessed before resolution"):
        _ = service.dependencies
