import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
    resolver.resolve_global_webhooks = AsyncMock(return_value={})
    return resolver, channel, cron


@pytest.mark.asyncio
async def test_run_resolves_channels_and_crons(mock_resolver):
    resolver, channel, cron = mock_resolver
    settings = MicroclawSettings()

    with patch("microclaw.service.DependencyResolver", return_value=resolver) as mock_resolver_cls:
        service = MicroclawService(settings=settings)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(service.run(), timeout=0.01)

    mock_resolver_cls.assert_called_once_with(settings=settings)
    resolver.resolve_channels.assert_awaited_once()
    resolver.resolve_crons.assert_awaited_once()
    resolver.resolve_global_webhooks.assert_awaited_once()


def test_dependencies_before_run_raises():
    settings = MicroclawSettings()
    service = MicroclawService(settings=settings)

    with pytest.raises(RuntimeError, match="Dependencies accessed before resolution"):
        _ = service.dependencies
