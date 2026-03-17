from types import NoneType

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .agents import Agent, AgentSettings, InputTypeEnum, MCPLocalSettings, MCPRemoteSettings, MCPSettings
from .channels import ChannelInterface, get_channel
from .sessions_storages import SessionsStorageInterface, get_sessions_storage
from .toolkits import BaseToolKit, ToolKitSettings, get_toolkit
from .toolkits.memory import MemoryToolKit
from .stt import STT, STTSettings
from .settings import MicroclawSettings
from .utils import get_by_key_or_first
from .cron import Cron, CronSettings


class DependencyResolver:
    def __init__(self, settings: MicroclawSettings):
        self._settings = settings
        self._sessions_storages: dict[str, SessionsStorageInterface] | None = None
        self._toolkits: dict[str, BaseToolKit] | None = None
        self._agents: dict[str, Agent] | None = None
        self._stt: dict[str, STT] | None = None
        self._channels: dict[str, ChannelInterface] | None = None
        self._crons: dict[str, Cron] | None = None

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
            agent_toolkits = toolkits
        else:
            agent_toolkits = {
                toolkit_key: get_toolkit(
                    key=toolkit_key,
                    toolkit_settings_or_path=toolkit_settings,
                )
                for toolkit_key, toolkit_settings in agent_settings.toolkits.items()
            }

        mcps = self._settings.mcp
        if agent_settings.mcp is None:
            mcps_settings = mcps.keys()
        else:
            mcps_settings = agent_settings.mcp
        agent_mcps_settings = []
        for mcp_settings_or_name in mcps_settings:
            if isinstance(mcp_settings_or_name, str) and mcp_settings_or_name in mcps:
                agent_mcps_settings.append(mcps[mcp_settings_or_name])
            elif isinstance(mcp_settings_or_name, MCPSettings):
                agent_mcps_settings.append(mcp_settings_or_name)
            else:
                raise ValueError(f"MCP with name '{mcp_settings_or_name}' not exists")
        mcp = await self.resolve_mcp(agent_mcps_settings)

        return Agent(
            settings=agent_settings,
            model_settings=model_settings,
            provider_settings=provider_settings,
            toolkits=agent_toolkits,
            mcp=mcp,
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
            for toolkit_key, toolkit_settings_or_path in self._settings.toolkits.items():
                self._toolkits[toolkit_key] = get_toolkit(
                    toolkit_settings_or_path=toolkit_settings_or_path,
                    key=toolkit_key,
                )
        return self._toolkits

    async def resolve_mcp(self, mcp_settings: list[MCPSettings]) -> MultiServerMCPClient:
        servers = {}
        for settings in mcp_settings:
            if isinstance(settings, MCPRemoteSettings):
                server_name = settings.name or settings.url
                mcp_data = {}
                if settings.url.startswith("http"):
                    mcp_data["transport"] = "http"
                elif settings.url.startswith("ws"):
                    mcp_data["transport"] = "ws"
                else:
                    raise ValueError(f"Incorrect MCP URL: {settings.url}")
                mcp_data["url"] = settings.url
            elif isinstance(settings, MCPLocalSettings):
                server_name = settings.name or " ".join((settings.command, *settings.args))
                mcp_data = {
                    "transport": "stdio",
                    "command": settings.command,
                    "args": settings.args,
                }
            else:
                raise ValueError(f"Unsupport MCP settings type: {type(settings)}")
            servers[server_name] = mcp_data

        return MultiServerMCPClient(servers)

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

    async def resolve_crons(self) -> dict[str, Cron]:
        if self._crons is None:
            self._crons = {
                key: await self.resolve_cron(cron_settings=cron_settings)
                for key, cron_settings in self._settings.cron.items()
            }
        return self._crons

    async def resolve_cron(self, cron_settings: CronSettings) -> Cron:
        channel_key = cron_settings.channel
        channel = get_by_key_or_first(storage=await self.resolve_channels(), key=channel_key)
        if channel is None:
            raise RuntimeError(f"Have no channel with name '{channel_key}'")

        return Cron(
            settings=cron_settings,
            channel=channel,
        )
