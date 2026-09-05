import os
import pathlib
from types import NoneType
from typing import Self

from .agents import (
    AgentSettings,
    APITypeEnum,
    InputTypeEnum,
    MCPSettings,
    ModelSettings,
    ProviderSettings,
)
from .api.rest import RESTAPISettings
from .channels.telegram.polling.settings import TelegramPollingSettings
from .channels.telegram.webhook.settings import TelegramWebhookSettings
from .channels.vk.polling.settings import VKPollingSettings
from .channels.vk.webhook.settings import VKWebhookSettings
from .cron import CronTaskSettings
from .sessions_storages import SessionsStorageSettingsType
from .sessions_storages.filesystem import FilesystemSessionsStorageSettings
from .skills import SkillRepositorySettingsType, SkillSettings
from .stt import STTSettings
from .syncers import SyncerSettingsType
from .syncers.memory import MemorySyncerSettings
from .toolkits import ToolKitSettings
from .users_storages import UsersStorageSettingsType
from .users_storages.filesystem import FilesystemUsersStorageSettings
from .utils import get_by_key_or_first
from .webhooks import WebhookSettings
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
import yaml
from yaml_env_tag import construct_env_tag
import yaml_include


ChannelSettingsType = (
    TelegramPollingSettings
    | TelegramWebhookSettings
    | VKPollingSettings
    | VKWebhookSettings
)


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    rotation: str = "10 MB"
    retention: str = "7 days"
    compression: str = "zip"
    path: str | None = None
    console: bool = True


class MicroclawSettings(BaseSettings):
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    rest: RESTAPISettings = Field(default_factory=RESTAPISettings)
    sessions_storages: dict[str, SessionsStorageSettingsType] = {
        "default": FilesystemSessionsStorageSettings(),
    }
    users_storages: dict[str, UsersStorageSettingsType] = {
        "default": FilesystemUsersStorageSettings(),
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
    skills_directory: pathlib.Path = pathlib.Path("./.skills")
    skills_repositories: dict[str, SkillRepositorySettingsType] = Field(
        default_factory=dict
    )
    skills: dict[str, SkillSettings | str] = Field(default_factory=dict)
    agents: dict[str, AgentSettings] = {
        "default": AgentSettings(),
    }
    stt: dict[str, STTSettings] = Field(default_factory=dict)
    channels: dict[str, ChannelSettingsType] = Field(default_factory=dict)
    syncer: SyncerSettingsType = Field(default_factory=MemorySyncerSettings)
    cron: dict[str, CronTaskSettings] = Field(default_factory=dict)
    webhooks: dict[str, WebhookSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate(self) -> Self:
        for name, model_settings in self.models.items():
            provider_value = model_settings.provider
            if isinstance(provider_value, (str, NoneType)):
                provider_value = get_by_key_or_first(
                    storage=self.providers, key=provider_value
                )
            if provider_value is None:
                raise ValueError(f"Provider for model '{name}' not exists")
            model_settings.provider = provider_value

        for name, agent_settings in self.agents.items():
            model_value = agent_settings.model
            if isinstance(model_value, (str, NoneType)):
                model_value = get_by_key_or_first(storage=self.models, key=model_value)
            if model_value is None:
                raise ValueError(f"Model for agent '{name}' not exists")
            if InputTypeEnum.TEXT not in model_value.input_types:
                raise ValueError(
                    f"Model '{model_value.id}' for agent '{name}' does not support text input. "
                    f"Supported input types: {[t.value for t in model_value.input_types]}"
                )
            agent_settings.model = model_value
            for toolkit_item in agent_settings.toolkits or []:
                if isinstance(toolkit_item, str) and toolkit_item not in self.toolkits and "." not in toolkit_item:
                    raise ValueError(
                        f"Agent '{name}' toolkit '{toolkit_item}' is "
                        "not a reference to a global toolkit and does not "
                        "look like a dotted import path"
                    )

        for name, channel_settings in self.channels.items():
            agent_value = channel_settings.agent
            if isinstance(agent_value, str):
                agent = get_by_key_or_first(storage=self.agents, key=agent_value)
                if agent is None:
                    raise ValueError(
                        f"Agent '{agent_value}' for channel '{name}' not exists"
                    )
            elif agent_value is None:
                if not self.agents:
                    raise ValueError(f"No agents defined for channel '{name}'")
            elif not isinstance(agent_value, AgentSettings):
                raise ValueError(
                    f"Invalid agent type for channel '{name}': {type(agent_value)}"
                )

            sessions_storage_value = channel_settings.sessions_storage
            if isinstance(sessions_storage_value, str):
                sessions_storage = get_by_key_or_first(
                    storage=self.sessions_storages,
                    key=sessions_storage_value,
                )
                if sessions_storage is None:
                    raise ValueError(
                        f"Sessions storage '{sessions_storage_value}' for channel '{name}' not exists"
                    )
            elif sessions_storage_value is None:
                if not self.sessions_storages:
                    raise ValueError(
                        f"No sessions storages defined for channel '{name}'"
                    )
            elif not isinstance(sessions_storage_value, SessionsStorageSettingsType):
                raise ValueError(
                    f"Invalid sessions_storage type for channel '{name}': {type(sessions_storage_value)}"
                )

            stt_value = channel_settings.stt
            if isinstance(stt_value, str):
                stt = get_by_key_or_first(storage=self.stt, key=stt_value)
                if stt is None:
                    raise ValueError(
                        f"STT '{stt_value}' for channel '{name}' not exists"
                    )
            elif isinstance(stt_value, STTSettings):
                model_value = stt_value.model
                if isinstance(model_value, (str, NoneType)):
                    model_value = get_by_key_or_first(
                        storage=self.models, key=model_value
                    )
                if model_value is None:
                    raise ValueError(
                        f"Model for inline STT in channel '{name}' not exists"
                    )
                if InputTypeEnum.AUDIO not in model_value.input_types:
                    raise ValueError(
                        f"Model '{model_value.id}' for inline STT in channel '{name}' does not support audio input. "
                        f"Supported input types: {[t.value for t in model_value.input_types]}"
                    )
                stt_value.model = model_value
            elif stt_value is not None:
                raise ValueError(
                    f"Invalid stt type for channel '{name}': {type(stt_value)}"
                )

            users_storage_value = channel_settings.users_storage
            if isinstance(users_storage_value, str):
                users_storage = get_by_key_or_first(
                    storage=self.users_storages,
                    key=users_storage_value,
                )
                if users_storage is None:
                    raise ValueError(
                        f"Users storage '{users_storage_value}' for channel '{name}' not exists"
                    )
            elif users_storage_value is None:
                if not self.users_storages:
                    raise ValueError(f"No users storages defined for channel '{name}'")
            elif not isinstance(users_storage_value, UsersStorageSettingsType):
                raise ValueError(
                    f"Invalid users_storage type for channel '{name}': {type(users_storage_value)}"
                )

        for name, stt_settings in self.stt.items():
            model_value = stt_settings.model
            if isinstance(model_value, (str, NoneType)):
                model_value = get_by_key_or_first(storage=self.models, key=model_value)
            if model_value is None:
                raise ValueError(f"Model for stt '{name}' not exists")
            if InputTypeEnum.AUDIO not in model_value.input_types:
                raise ValueError(
                    f"Model '{model_value.id}' for stt '{name}' does not support audio input. "
                    f"Supported input types: {[t.value for t in model_value.input_types]}"
                )
            stt_settings.model = model_value

        toolkit_names = set()
        for toolkit_settings in self.toolkits.values():
            if isinstance(toolkit_settings, str) or toolkit_settings.name is None:
                continue
            if toolkit_settings.name in toolkit_names:
                raise ValueError(
                    f"Toolkits must be have unique names. Name '{toolkit_settings.name}' "
                    "already defined"
                )
            toolkit_names.add(toolkit_settings.name)

        mcp_names = set()
        for name, mcp_settings in self.mcp.items():
            if mcp_settings.name is None:
                continue
            if mcp_settings.name in mcp_names:
                raise ValueError(
                    f"MCP servers must have unique names. Name '{mcp_settings.name}' "
                    "already defined"
                )
            mcp_names.add(mcp_settings.name)

        for skill_name, skill_value in self.skills.items():
            if isinstance(skill_value, SkillSettings) and isinstance(
                skill_value.repo, str
            ):
                if skill_value.repo not in self.skills_repositories:
                    raise ValueError(
                        f"Global skill '{skill_name}' references repository "
                        f"'{skill_value.repo}' which is not defined in skills_repositories"
                    )

        for agent_name, agent_settings in self.agents.items():
            if not agent_settings.skills:
                continue
            for skill_item in agent_settings.skills:
                if isinstance(skill_item, SkillSettings) and isinstance(
                    skill_item.repo, str
                ):
                    if skill_item.repo not in self.skills_repositories:
                        raise ValueError(
                            f"Agent '{agent_name}' skill '{skill_item.name}' "
                            f"references repository '{skill_item.repo}' which is not "
                            f"defined in skills_repositories"
                        )

        webhook_paths = set()
        for name, webhook_settings in self.webhooks.items():
            if webhook_settings.path in webhook_paths:
                raise ValueError(
                    f"Webhook path collision: '{webhook_settings.path}'"
                )
            webhook_paths.add(webhook_settings.path)

            agent_value = webhook_settings.args.get("agent")
            if isinstance(agent_value, str):
                agent = get_by_key_or_first(storage=self.agents, key=agent_value)
                if agent is None:
                    raise ValueError(
                        f"Agent '{agent_value}' for webhook '{name}' not exists"
                    )

            channel_value = webhook_settings.args.get("channel")
            if isinstance(channel_value, str):
                channel = get_by_key_or_first(storage=self.channels, key=channel_value)
                if channel is None:
                    raise ValueError(
                        f"Channel '{channel_value}' for webhook '{name}' not exists"
                    )

        return self

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
