import functools
import json
import random
import string
from typing import Any, Callable, Generic, TypeVar

from langchain_core.tools import StructuredTool as LangChainStructuredTool
from pydantic import BaseModel

from .settings import ToolKitSettings


SettingsType = TypeVar("SettingsType")


class EmptySettings(BaseModel):
    pass


class BaseToolKit(Generic[SettingsType]):
    DESCRIPTION: str | None = None

    def __init__(self, settings: ToolKitSettings):
        self._name = settings.name or settings.path
        self._prefix = (settings.name or _get_random_string()) + "_"
        self._extra_info = settings.extra_info
        self._settings = self.get_settings_class()(**settings.args)

    @property
    def name(self) -> str:
        return self._name

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def description(self) -> str | None:
        return self.DESCRIPTION

    @property
    def extra_info(self) -> str | None:
        return self._extra_info

    @property
    def settings(self) -> SettingsType:
        return self._settings

    @classmethod
    def get_settings_class(cls) -> SettingsType | type[EmptySettings]:
        for base in cls.__orig_bases__:
            origin = getattr(base, "__origin__", None)
            if isinstance(origin, type) and issubclass(origin, BaseToolKit):
                return base.__args__[0]
        return EmptySettings

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
    def convert(item) -> dict[str, Any] | None:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, list):
            return [convert(element) for element in item]
        if isinstance(item, str):
            return json.loads(item)

    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        try:
            result = await function(*args, **kwargs)
        except BaseException as exception:
            return {"success": False, "exception": str(exception)}
        return convert(item=result)

    return wrapper
