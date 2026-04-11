import os
import pathlib
from types import NoneType
from typing import Self

import yaml
import yaml_include
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
from yaml_env_tag import construct_env_tag

from .agents import (
    APITypeEnum,
    AgentSettings,
    InputTypeEnum,
    MCPSettings,
    ModelSettings,
    ProviderSettings,
)
from .toolkits import ToolKitSettings
from .channels import ChannelSettingsType
from .sessions_storages import SessionsStorageSettingsType
from .sessions_storages.filesystem import FilesystemSessionsStorageSettings
from .stt import STTSettings
from .cron import CronSettings
from .utils import get_by_key_or_first


class MicroclawSettings(BaseSettings):
    sessions_storages: dict[str, SessionsStorageSettingsType] = {
        "default": FilesystemSessionsStorageSettings(),
    }
    providers: dict[str, ProviderSettings] = {
        "default": ProviderSettings(
            base_url="https://api.openai.com/v1",
            api_type=APITypeEnum.OPENAI,
            api_key=os.environ.get("OPENAI_API_KEY") or None,
        ),
    }
    models: dict[str, ModelSettings] = {
        "default": ModelSettings(id="gpt-4o"),
    }
    toolkits: dict[str, ToolKitSettings] = Field(default_factory=dict)
    mcp: dict[str, MCPSettings] = Field(default_factory=dict)
    agents: dict[str, AgentSettings] = {
        "default": AgentSettings(),
    }
    stt: dict[str, STTSettings] = Field(default_factory=dict)
    channels: dict[str, ChannelSettingsType] = Field(default_factory=dict)
    cron: dict[str, CronSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    @classmethod
    def validate(cls, settings: Self) -> Self:
        for name, model_settings in settings.models.items():
            provider_value = model_settings.provider
            if isinstance(provider_value, (str, NoneType)):
                provider_value = get_by_key_or_first(storage=settings.providers, key=provider_value)
            if provider_value is None:
                raise ValueError(f"Provider for model '{name}' not exists")
            model_settings.provider = provider_value

        for name, agent_settings in settings.agents.items():
            model_value = agent_settings.model
            if isinstance(model_value, (str, NoneType)):
                model_value = get_by_key_or_first(storage=settings.models, key=model_value)
            if model_value is None:
                raise ValueError(f"Model for agent '{name}' not exists")
            if InputTypeEnum.TEXT not in model_value.input_types:
                raise ValueError(
                    f"Model '{model_value.id}' for agent '{name}' does not support text input. "
                    f"Supported input types: {[t.value for t in model_value.input_types]}"
                )
            agent_settings.model = model_value

        for name, channel_settings in settings.channels.items():
            agent_key = channel_settings.agent
            agent = get_by_key_or_first(storage=settings.agents, key=agent_key)
            if agent is None:
                raise ValueError(f"Agent for channel '{name}' not exists")

            sessions_storage_key = channel_settings.sessions_storage
            sessions_storage = get_by_key_or_first(
                storage=settings.sessions_storages,
                key=sessions_storage_key,
            )
            if sessions_storage is None:
                raise ValueError(f"Sessions storage for channel '{name}' not set or not exists")

        for name, stt_settings in settings.stt.items():
            model_value = stt_settings.model
            if isinstance(model_value, (str, NoneType)):
                model_value = get_by_key_or_first(storage=settings.models, key=model_value)
            if model_value is None:
                raise ValueError(f"Model for stt '{name}' not exists")
            if InputTypeEnum.AUDIO not in model_value.input_types:
                raise ValueError(
                    f"Model '{model_value.id}' for stt '{name}' does not support audio input. "
                    f"Supported input types: {[t.value for t in model_value.input_types]}"
                )
            stt_settings.model = model_value

        toolkit_names = set()
        for toolkit_settings in settings.toolkits:
            if isinstance(toolkit_settings, str) or toolkit_settings.name is None:
                continue
            if toolkit_settings.name in toolkit_names:
                raise ValueError(
                    f"Toolkits must be have unique names. Name '{toolkit_settings.name}' "
                    "already defined"
                )

        mcp_names = set()
        for name, mcp_settings in settings.mcp.items():
            if mcp_settings.name is None:
                continue
            if mcp_settings.name in mcp_names:
                raise ValueError(
                    f"MCP servers must have unique names. Name '{mcp_settings.name}' "
                    "already defined"
                )
            mcp_names.add(mcp_settings.name)

        return settings

    @classmethod
    def load(
            cls,
            env_prefix: str | None = None,
            env_file: pathlib.Path | None = None,
            config_file: pathlib.Path | None = None,
    ) -> Self:
        data = {}

        if config_file is not None:
            yaml_loader = cls.get_yaml_loader(base_path=str(config_file.parent))
            with config_file.open() as _file:
                data.update(yaml.load(_file, Loader=yaml_loader))

        return cls(
            **data,
            _env_prefix=env_prefix,
            _env_file=env_file,
        )

    @staticmethod
    def get_yaml_loader(base_path: pathlib.Path) -> yaml.BaseLoader:
        yaml_loader_class = type("YAMLLoader", (yaml.SafeLoader,), {})
        yaml_loader_class.add_constructor(
            "!include",
            yaml_include.Constructor(base_dir=str(base_path)),
        )
        yaml_loader_class.add_constructor(
            "!env",
            construct_env_tag,
        )

        return yaml_loader_class
