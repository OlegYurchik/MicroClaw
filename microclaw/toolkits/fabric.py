import importlib

from .base import BaseToolKit
from .settings import ToolKitSettings


def get_toolkit(
        toolkit_settings_or_path: ToolKitSettings | str,
) -> BaseToolKit:
    if isinstance(toolkit_settings_or_path, str):
        toolkit_settings = ToolKitSettings(path=toolkit_settings_or_path)
    else:
        toolkit_settings = toolkit_settings_or_path

    toolkit_module_path, toolkit_class_name = toolkit_settings.path.rsplit(".", 1)
    toolkit_module = importlib.import_module(toolkit_module_path)

    if not hasattr(toolkit_module, toolkit_class_name):
        raise ValueError(
            f"Tool kit class '{toolkit_class_name}' not found in module '{toolkit_module_path}'",
        )
    toolkit_class = getattr(toolkit_module, toolkit_class_name)
    if not issubclass(toolkit_class, BaseToolKit):
        raise TypeError(f"Class '{toolkit_class_name}' is not a tool kit")

    return toolkit_class(settings=toolkit_settings)
