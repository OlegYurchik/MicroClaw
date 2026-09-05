import importlib

from microclaw.webhooks.base import BaseWebhook
from microclaw.webhooks.settings import WebhookSettings


async def get_webhook(
    settings: WebhookSettings,
    resolver: "DependencyResolver",  # noqa: F821
) -> BaseWebhook:
    module_path, class_name = settings.path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    webhook_class = getattr(module, class_name)
    if not issubclass(webhook_class, BaseWebhook):
        raise ValueError(f"Class {class_name} is not a subclass of BaseWebhook")

    arguments = webhook_class.get_settings_class()(**settings.args)
    return webhook_class(arguments=arguments, resolver=resolver)
