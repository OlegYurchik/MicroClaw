import importlib

from microclaw.cron.base import BaseCronTask
from microclaw.cron.settings import CronTaskSettings


async def get_cron_task(
    key: str,
    settings: CronTaskSettings,
    resolver: "DependencyResolver",  # noqa: F821
) -> BaseCronTask:
    module_path, class_name = settings.path.rsplit(".", 1)

    module = importlib.import_module(module_path)
    task_class = getattr(module, class_name)
    if not issubclass(task_class, BaseCronTask):
        raise ValueError(f"Class {class_name} is not a subclass of BaseCronTask")

    return task_class(key=key, settings=settings, resolver=resolver)
