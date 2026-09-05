import uuid

from .channels import BaseChannel
from .cron import BaseCronTask
from .resolver import DependencyResolver
from .settings import MicroclawSettings
from .webhooks import BaseWebhook
import facet


class MicroclawService(facet.AsyncioServiceMixin):
    def __init__(self, settings: MicroclawSettings):
        self._resolver = DependencyResolver(settings=settings)
        self._channels: dict[str, BaseChannel] | None = None
        self._crons: dict[str, BaseCronTask] | None = None
        self._global_webhooks: dict[uuid.UUID, BaseWebhook] | None = None

    async def run(self) -> None:
        self._channels = await self._resolver.resolve_channels()
        self._crons = await self._resolver.resolve_crons()
        self._global_webhooks = await self._resolver.resolve_global_webhooks()
        await super().run()

    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]:
        if self._channels is None or self._crons is None:
            raise RuntimeError(
                "Dependencies accessed before resolution. "
                "Run the service via 'await service.run()'."
            )
        return [
            *self._channels.values(),
            *self._crons.values(),
        ]
