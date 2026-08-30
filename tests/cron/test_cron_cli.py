from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.cron.cli import CronRunnerService, get_cron_services


class TestGetCronServices:
    async def test_get_cron_services_success(self):
        settings = MagicMock()
        resolver = MagicMock()
        task = MagicMock()
        resolver.resolve_crons = AsyncMock(return_value={"task_key": task})

        service = await get_cron_services(settings=settings, resolver=resolver)
        assert isinstance(service, CronRunnerService)
        assert task in service.dependencies
        resolver.resolve_crons.assert_awaited()

    async def test_get_cron_services_empty_raises(self):
        settings = MagicMock()
        resolver = MagicMock()
        resolver.resolve_crons = AsyncMock(return_value={})

        with pytest.raises(ValueError, match="cron tasks"):
            await get_cron_services(settings=settings, resolver=resolver)

    async def test_get_cron_services_creates_resolver(self):
        settings = MagicMock()
        task = MagicMock()
        resolver = MagicMock()
        resolver.resolve_crons = AsyncMock(return_value={"task_key": task})

        service = await get_cron_services(settings=settings, resolver=resolver)
        assert service.dependencies
