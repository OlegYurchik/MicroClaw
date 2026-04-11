import functools
import json
import random
import string
from typing import Any, Callable, Generic, TypeVar

from langchain_core.tools import StructuredTool as LangChainStructuredTool
from pydantic import BaseModel, create_model

from .settings import ToolKitSettings


SettingsType = TypeVar("SettingsType")


class EmptySettings(BaseModel):
    pass


class BaseToolKit(Generic[SettingsType]):
    def __init__(self, key: str, settings: ToolKitSettings):
        self._prefix = key + "_"
        self._prompt = settings.prompt
        self._settings = self.get_settings_class()(**settings.args)

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
    def convert(response) -> Any | None:
        if isinstance(response, BaseModel):
            return response.model_dump(mode="json")
        if isinstance(response, list):
            return [convert(response=element) for element in response]
        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return response
        return response

    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        return convert(response=await function(*args, **kwargs))

    return wrapper
