from types import NoneType

from .agents import Agent, AgentSettings, InputTypeEnum
from .channels import ChannelInterface, get_channel
from .sessions_storages import SessionsStorageInterface, get_sessions_storage
from .toolkits import BaseToolKit, get_toolkit
from .stt import STT, STTSettings
from .settings import MicroclawSettings
from .utils import get_by_key_or_first


class DependencyResolver:
    def __init__(self, settings: MicroclawSettings):
        self._settings = settings
        self._sessions_storages: dict[str, SessionsStorageInterface] | None = None
        self._toolkits: dict[str, BaseToolKit] | None = None
        self._agents: dict[str, Agent] | None = None
        self._stt: dict[str, STT] | None = None
        self._channels: dict[str, ChannelInterface] | None = None

    async def resolve_channels(self) -> dict[str, ChannelInterface]:
        if self._channels is None:
            self._channels = {
                key: await self.resolve_channel(
                    channel_key=key,
                    channel_settings=channel_settings,
                )
                for key, channel_settings in self._settings.channels.items()
            }
        return self._channels

    async def resolve_channel(
            self,
            channel_key: str,
            channel_settings: ChannelInterface,
    ) -> ChannelInterface:
        sessions_storage_key = channel_settings.sessions_storage
        sessions_storage = get_by_key_or_first(
            storage=await self.resolve_sessions_storages(),
            key=sessions_storage_key,
        )
        if sessions_storage is None:
            raise RuntimeError(f"Have no sessions storage with name '{sessions_storage_key}'")

        agent_key = channel_settings.agent
        agent = get_by_key_or_first(storage=await self.resolve_agents(), key=agent_key)
        if agent is None:
            raise RuntimeError(f"Have no agent with name '{agent_key}'")

        stt_key = channel_settings.stt
        stt = get_by_key_or_first(storage=await self.resolve_stts(), key=stt_key)

        return get_channel(
            settings=channel_settings,
            sessions_storage=sessions_storage,
            agent=agent,
            stt=stt,
            channel_key=channel_key,
        )

    async def resolve_agents(self) -> dict[str, Agent]:
        if self._agents is None:
            self._agents = {
                key: await self.resolve_agent(agent_settings=agent_settings)
                for key, agent_settings in self._settings.agents.items()
            }
        return self._agents

    async def resolve_agent(self, agent_settings: AgentSettings) -> Agent:
        model_settings = agent_settings.model
        if isinstance(model_settings, (str, NoneType)):
            model_settings = get_by_key_or_first(storage=self._settings.models, key=model_settings)
        if model_settings is None:
            raise RuntimeError(f"Have no model with name '{agent_settings.model}'")

        provider_settings = model_settings.provider
        if isinstance(provider_settings, (str, NoneType)):
            provider_settings = get_by_key_or_first(
                storage=self._settings.providers,
                key=provider_settings,
            )
        if provider_settings is None:
            raise RuntimeError(f"Have no provider with name '{model_settings.provider}'")

        if InputTypeEnum.TEXT not in model_settings.input_types:
            raise RuntimeError(
                f"Model '{model_settings.id}' does not support text input. "
                f"Supported input types: {[t.value for t in model_settings.input_types]}"
            )

        toolkits = await self.resolve_toolkits()
        if agent_settings.toolkits is None:
            toolkits_settings = toolkits.keys()
        else:
            toolkits_settings = agent_settings.toolkits
        agent_toolkits = []
        for toolkit_settings_or_path in toolkits_settings:
            if isinstance(toolkit_settings_or_path, str) and toolkit_settings_or_path in toolkits:
                toolkit = toolkits[toolkit_settings_or_path]
            else:
                toolkit = get_toolkit(toolkit_settings_or_path=toolkit_settings_or_path)
            agent_toolkits.append(toolkit)

        return Agent(
            settings=agent_settings,
            model_settings=model_settings,
            provider_settings=provider_settings,
            toolkits=agent_toolkits,
        )

    async def resolve_sessions_storages(self) -> dict[str, SessionsStorageInterface]:
        if self._sessions_storages is None:
            self._sessions_storages = {
                key: get_sessions_storage(settings=sessions_storage_settings)
                for key, sessions_storage_settings in self._settings.sessions_storages.items()
            }
        return self._sessions_storages

    async def resolve_toolkits(self) -> dict[str, BaseToolKit]:
        if self._toolkits is None:
            self._toolkits = {}
            for toolkit_settings_or_path in self._settings.toolkits:
                if isinstance(toolkit_settings_or_path, str):
                    toolkit_key = toolkit_settings_or_path
                else:
                    toolkit_key = toolkit_settings_or_path.name or toolkit_settings_or_path.path
                self._toolkits[toolkit_key] = get_toolkit(
                    toolkit_settings_or_path=toolkit_settings_or_path,
                )
        return self._toolkits

    async def resolve_stts(self) -> dict[str, STT]:
        if self._stt is None:
            self._stt = {
                key: await self.resolve_stt(stt_settings=stt_settings)
                for key, stt_settings in self._settings.stt.items()
            }
        return self._stt

    async def resolve_stt(self, stt_settings: STTSettings) -> STT:
        model_settings = stt_settings.model
        if isinstance(model_settings, (str, NoneType)):
            model_settings = get_by_key_or_first(storage=self._settings.models, key=model_settings)
        if model_settings is None:
            raise RuntimeError(f"Have no model with name '{stt_settings.model}'")

        provider_settings = model_settings.provider
        if isinstance(provider_settings, (str, NoneType)):
            provider_settings = get_by_key_or_first(
                storage=self._settings.providers,
                key=provider_settings,
            )
        if provider_settings is None:
            raise RuntimeError(f"Have no provider with name '{model_settings.provider}'")

        if InputTypeEnum.AUDIO not in model_settings.input_types:
            raise RuntimeError(
                f"Model '{model_settings.id}' does not support audio input. "
                f"Supported input types: {[t.value for t in model_settings.input_types]}"
            )

        return STT(
            settings=stt_settings,
            model_settings=model_settings,
            provider_settings=provider_settings,
        )
