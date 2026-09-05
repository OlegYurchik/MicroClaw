from collections.abc import Callable, Sequence
import functools
import random
import string
from typing import Any, Generic, TypeVar, get_args, get_origin
import uuid

from .capabilities import DiscoveryCapability, ToolKitCapability
from .settings import ToolKitSettings
from langchain_core.tools import StructuredTool as LangChainStructuredTool
from pydantic import BaseModel


ArgumentsType = TypeVar("ArgumentsType")


class EmptySettings(BaseModel):
    pass


class BaseToolKit(Generic[ArgumentsType]):
    required_capabilities: Sequence[ToolKitCapability] = ()
    write_capabilities: Sequence[ToolKitCapability] = ()
    discovery_capabilities: Sequence[DiscoveryCapability] = ()

    def __init__(self, key: str, settings: ToolKitSettings):
        self._settings = settings
        self._prefix = key + "_"
        self._prompt = settings.prompt
        self._arguments = self.get_settings_class()(**settings.args)

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
    def arguments(self) -> ArgumentsType:
        return self._arguments

    @classmethod
    def get_settings_class(cls) -> ArgumentsType | type[EmptySettings]:
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


class AgentSettingsMixin:
    """Mixin for toolkits that need to load/save per-user agent settings."""

    async def _resolve_target_user_id(self, user_id: str | None) -> uuid.UUID | None:
        if user_id is None:
            return None
        ctx = self._require_context()
        if ctx.all_users_accessor is None:
            raise PermissionError("Cross-user access not granted")
        return uuid.UUID(user_id)

    async def _require_cross_user_write(self) -> None:
        ctx = self._require_context()
        if ctx.all_users_accessor is None:
            raise PermissionError("Cross-user access not granted")
        if not ctx.all_users_accessor.writable:
            raise PermissionError("Cross-user write access not granted")

    async def _load_agent_settings(
        self, target_user_id: uuid.UUID | None = None
    ) -> Any:
        from microclaw.agents.settings import AgentSettings

        ctx = self._require_context()
        if target_user_id is None:
            user = await ctx.current_user_accessor.get()
        else:
            if ctx.all_users_accessor is None:
                raise PermissionError("Cross-user access not granted")
            user = await ctx.all_users_accessor.get_by_id(target_user_id)
        if user is None:
            raise RuntimeError("User not found")
        if user.agent:
            return AgentSettings.model_validate(user.agent)
        if ctx.channel_agent_settings:
            return AgentSettings.model_validate(ctx.channel_agent_settings)
        return AgentSettings()

    async def _save_agent_settings(
        self,
        agent_settings: Any,
        target_user_id: uuid.UUID | None = None,
    ) -> None:
        from microclaw.agents.settings import AgentSettings

        ctx = self._require_context()

        def _merge_with_channel(base: Any) -> Any:
            if ctx.channel_agent_settings is None:
                return base
            merged = AgentSettings.model_validate(ctx.channel_agent_settings)
            for field_name in AgentSettings.model_fields:
                override_value = getattr(base, field_name)
                if override_value is not None:
                    setattr(merged, field_name, override_value)
            return merged

        if target_user_id is None:
            user = await ctx.current_user_accessor.get()
            if user is None:
                raise RuntimeError("User not found")
            if user.agent is None and ctx.channel_agent_settings is not None:
                agent_settings = _merge_with_channel(agent_settings)
            validated = AgentSettings.model_validate(
                agent_settings.model_dump(mode="json")
            )
            await ctx.current_user_accessor.update_agent_settings(validated)
        else:
            if ctx.all_users_accessor is None:
                raise PermissionError("Cross-user access not granted")
            if not ctx.all_users_accessor.writable:
                raise PermissionError("Cross-user write access not granted")
            user = await ctx.all_users_accessor.get_by_id(target_user_id)
            if user is None:
                raise RuntimeError("User not found")
            if user.agent is None and ctx.channel_agent_settings is not None:
                agent_settings = _merge_with_channel(agent_settings)
            validated = AgentSettings.model_validate(
                agent_settings.model_dump(mode="json")
            )
            await ctx.all_users_accessor.update_agent_settings(
                target_user_id, validated
            )
