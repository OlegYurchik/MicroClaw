
from pydantic import BaseModel
import pytest

from microclaw.webhooks.base import BaseWebhook, WebhookResponse


class SamplePayload(BaseModel):
    message: str


class SampleSettings(BaseModel):
    prefix: str = "test"


class SampleWebhook(BaseWebhook[SampleSettings, SamplePayload]):
    async def handle(self, payload: SamplePayload) -> WebhookResponse | None:
        return WebhookResponse(body={"message": f"{self._arguments.prefix}: {payload.message}"})


@pytest.fixture
def test_webhook():
    return SampleWebhook(
        arguments=SampleSettings(prefix="hello"),
        resolver=None,  # type: ignore[arg-type]
    )


class TestBaseWebhook:
    @pytest.mark.asyncio
    async def test_get_payload_class(self, test_webhook):
        payload_class = test_webhook.get_payload_class()
        assert payload_class is SamplePayload

    @pytest.mark.asyncio
    async def test_get_settings_class(self, test_webhook):
        settings_class = SampleWebhook.get_settings_class()
        assert settings_class is SampleSettings

    @pytest.mark.asyncio
    async def test_call_validates_payload(self, test_webhook):
        result = await test_webhook({"message": "world"})
        assert result is not None
        assert result.body == {"message": "hello: world"}

    @pytest.mark.asyncio
    async def test_call_invalid_payload_raises(self, test_webhook):
        with pytest.raises(Exception):
            await test_webhook({"invalid_field": "world"})

    @pytest.mark.asyncio
    async def test_handle_returns_result(self, test_webhook):
        payload = SamplePayload(message="test")
        result = await test_webhook.handle(payload)
        assert result is not None
        assert result.body == {"message": "hello: test"}
