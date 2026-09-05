from pydantic import BaseModel
import pytest

from microclaw.webhooks import BaseWebhook, WebhookSettings, get_webhook
from microclaw.webhooks.base import WebhookResponse


class DummyPayload(BaseModel):
    value: str


class DummySettings(BaseModel):
    name: str = "default"


class DummyWebhook(BaseWebhook[DummySettings, DummyPayload]):
    async def handle(self, payload: DummyPayload) -> WebhookResponse | None:
        return WebhookResponse(body={"result": f"{self._arguments.name}: {payload.value}"})


@pytest.fixture
def resolver_mock():
    from unittest.mock import AsyncMock

    return AsyncMock()


class TestGetWebhook:
    @pytest.mark.asyncio
    async def test_get_webhook_instantiates_class(self, resolver_mock):
        settings = WebhookSettings(
            path="tests.webhooks.test_webhook_fabric.DummyWebhook",
            enabled=True,
            args={"name": "test_name"},
        )
        webhook = await get_webhook(settings=settings, resolver=resolver_mock)
        assert type(webhook).__name__ == "DummyWebhook"
        assert issubclass(type(webhook), BaseWebhook)
        assert webhook._arguments.name == "test_name"

    @pytest.mark.asyncio
    async def test_get_webhook_not_subclass_raises(self, resolver_mock):
        settings = WebhookSettings(
            path="tests.webhooks.test_webhook_fabric.DummySettings",
            enabled=True,
            args={},
        )
        with pytest.raises(ValueError, match="is not a subclass of BaseWebhook"):
            await get_webhook(settings=settings, resolver=resolver_mock)

    @pytest.mark.asyncio
    async def test_get_webhook_empty_args_uses_defaults(self, resolver_mock):
        settings = WebhookSettings(
            path="tests.webhooks.test_webhook_fabric.DummyWebhook",
            enabled=True,
            args={},
        )
        webhook = await get_webhook(settings=settings, resolver=resolver_mock)
        assert type(webhook).__name__ == "DummyWebhook"
        assert issubclass(type(webhook), BaseWebhook)
        assert webhook._arguments.name == "default"
