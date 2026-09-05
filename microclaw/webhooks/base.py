from typing import Any, Generic, TypeVar, get_args, get_origin

from pydantic import BaseModel, Field


ArgumentsType = TypeVar("ArgumentsType")
PayloadType = TypeVar("PayloadType", bound=BaseModel)


class EmptyArguments(BaseModel):
    pass


class WebhookResponse(BaseModel):
    status_code: int = 200
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None


class BaseWebhook(Generic[ArgumentsType, PayloadType]):
    def __init__(
        self,
        arguments: ArgumentsType,
        resolver: "DependencyResolver",  # noqa: F821
    ):
        self._arguments = arguments
        self._resolver = resolver

    async def __call__(self, data: dict[str, Any]) -> "WebhookResponse | None":
        payload_class = self.get_payload_class()
        payload = payload_class(**data)
        return await self.handle(payload=payload)

    @classmethod
    def get_settings_class(cls) -> type[ArgumentsType] | type[EmptyArguments]:
        for base in cls.__orig_bases__:
            origin = get_origin(base)
            if isinstance(origin, type) and issubclass(origin, BaseWebhook):
                args = get_args(base)
                if args:
                    return args[0]
        return EmptyArguments

    @classmethod
    def get_payload_class(cls) -> type[PayloadType]:
        for base in cls.__orig_bases__:
            origin = get_origin(base)
            if isinstance(origin, type) and issubclass(origin, BaseWebhook):
                args = get_args(base)
                if len(args) >= 2:
                    return args[1]
        raise RuntimeError("Cannot find PayloadType for Webhook")

    async def handle(self, payload: PayloadType) -> "WebhookResponse | None":
        raise NotImplementedError
