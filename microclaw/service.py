import asyncio

import facet

from .channels import BaseChannel
from .resolver import DependencyResolver
from .settings import MicroclawSettings


class MicroclawService(facet.AsyncioServiceMixin):
    def __init__(self, settings: MicroclawSettings):
        self._resolver = DependencyResolver(settings=settings)
        self._channels: dict[str, BaseChannel] = asyncio.run(
            self._resolver.resolve_channels(),
        )
        self._crons: dict[str, Cron] = asyncio.run(
            self._resolver.resolve_crons(),
        )

    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]:
        return [
            *self._channels.values(),
            *self._crons.values(),
        ]
