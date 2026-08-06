from __future__ import annotations
import functools
import random
import string
from typing import Any, Callable, Generic, Sequence, TypeVar, get_args, get_origin

from langchain_core.tools import StructuredTool as LangChainStructuredTool
from pydantic import BaseModel

from .capabilities import DiscoveryCapability, ToolKitCapability
from .settings import ToolKitSettings




SettingsType = TypeVar("SettingsType")


class EmptySettings(BaseModel):
    pass


class BaseToolKit(Generic[SettingsType]):
    required_capabilities: Sequence[ToolKitCapability] = ()
    write_capabilities: Sequence[ToolKitCapability] = ()
    discovery_capabilities: Sequence[DiscoveryCapability] = ()

    def __init__(self, key: str, settings: ToolKitSettings):
        self._prefix = key + "_"
        self._prompt = settings.prompt
        self._settings = self.get_settings_class()(**settings.args)

        # Override class defaults with instance settings if provided
        self.required_capabilities = (
            list(settings.required_capabilities)
            if settings.required_capabilities is not None
            else list(self.__class__.required_capabilities)
        )
        self.write_capabilities = (
            list(settings.write_capabilities)
            if settings.write_capabilities is not None
            else list(self.__class__.write_capabilities)
        )
        self.discovery_capabilities = (
            list(settings.discovery_capabilities)
            if settings.discovery_capabilities is not None
            else list(self.__class__.discovery_capabilities)
        )

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def description(self) -> str | None:
        return self.__doc__

    @property
    def prompt(self) -> str | None:
        return self._prompt

    @property
    def settings(self) -> SettingsType:
        return self._settings

    @classmethod
    def get_settings_class(cls) -> SettingsType | type[EmptySettings]:
        for base in cls.__orig_bases__:
            origin = get_origin(base)
            if isinstance(origin, type) and issubclass(origin, BaseToolKit):
                args = get_args(base)
                if args:
                    return args[0]
        return EmptySettings

    def _require_context(self):
        """Return toolkit context or raise if unavailable."""
        from .context import get_toolkit_context

        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        return ctx

    def get_tools(self) -> list[LangChainStructuredTool]:
        tool_functions = []
        for attribute_name in dir(self):
            attribute = getattr(self, attribute_name)
            if getattr(attribute, "_is_tool", False):
                tool_functions.append(attribute)
        return [
            LangChainStructuredTool.from_function(
                name=self.prefix + tool_function.__name__,
                description=tool_function.__doc__,
                coroutine=_return_dict(tool_function),
            )
            for tool_function in tool_functions
        ]


def tool(function: Callable) -> Callable:
    function._is_tool = True
    return function


def _get_random_string(
    length: int = 8,
    alphabet: str = string.ascii_lowercase + string.digits,
) -> str:
    return "".join(random.choice(alphabet) for _ in range(length))


def _return_dict(function: Callable) -> Callable:
    def convert(response) -> Any | None:
        if isinstance(response, BaseModel):
            return response.model_dump(mode="json")
        if isinstance(response, list):
            return [convert(response=element) for element in response]
        return response

    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        return convert(response=await function(*args, **kwargs))

    return wrapper
