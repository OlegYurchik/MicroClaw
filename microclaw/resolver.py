from types import NoneType

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .agents import Agent, AgentSettings, InputTypeEnum, MCPLocalSettings, MCPRemoteSettings, MCPSettings
from .agents.subagents.settings import SubAgentSettings
from .agents.subagents.toolkit import SubAgentToolKit
from .channels import BaseChannel, get_channel
from .cron import BaseCronTask, CronTaskSettings, get_cron_task
from .sessions_storages import (
    SessionsStorageInterface,
    SessionsStorageSettingsType,
    get_sessions_storage,
)
from .toolkits import BaseToolKit, ToolKitSettings, get_toolkit
from .stt import STT, STTSettings
from .syncers import SyncerInterface, get_syncer
from .users_storages import UsersStorageInterface, UsersStorageSettingsType, get_users_storage
from .settings import MicroclawSettings
from .utils import get_by_key_or_first


class DependencyResolver:
    def __init__(self, settings: MicroclawSettings):
        self._settings = settings
        self._sessions_storages: dict[str, SessionsStorageInterface] | None = None
        self._toolkits: dict[str, BaseToolKit] | None = None
        self._agents: dict[str, Agent] | None = None
        self._stt: dict[str, STT] | None = None
        self._channels: dict[str, BaseChannel] | None = None
        self._crons: dict[str, BaseCronTask] | None = None
        self._syncer: SyncerInterface | None = None
        self._users_storages: dict[str, UsersStorageInterface] | None = None

    async def resolve_channels(self) -> dict[str, BaseChannel]:
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
            channel_settings: BaseChannel,
    ) -> BaseChannel:
        sessions_storage_key_or_settings = channel_settings.sessions_storage
        if isinstance(sessions_storage_key_or_settings, str):
            sessions_storage = get_by_key_or_first(
                storage=await self.resolve_sessions_storages(),
                key=sessions_storage_key_or_settings,
            )
            if sessions_storage is None:
                raise RuntimeError(f"Have no sessions storage with name '{sessions_storage_key_or_settings}'")
        elif isinstance(sessions_storage_key_or_settings, SessionsStorageSettingsType):
            sessions_storage = get_sessions_storage(settings=sessions_storage_key_or_settings)
        else:
            sessions_storage = get_by_key_or_first(
                storage=await self.resolve_sessions_storages(),
                key=None,
            )

        agent_key_or_settings = channel_settings.agent
        if isinstance(agent_key_or_settings, str):
            agent = get_by_key_or_first(storage=await self.resolve_agents(), key=agent_key_or_settings)
            if agent is None:
                raise RuntimeError(f"Have no agent with name '{agent_key_or_settings}'")
        elif isinstance(agent_key_or_settings, AgentSettings):
            agent = await self.resolve_agent(agent_settings=agent_key_or_settings)
        else:
            agent = get_by_key_or_first(storage=await self.resolve_agents(), key=None)

        stt_key_or_settings = channel_settings.stt
        if isinstance(stt_key_or_settings, str):
            stt = get_by_key_or_first(storage=await self.resolve_stts(), key=stt_key_or_settings)
        elif isinstance(stt_key_or_settings, STTSettings):
            stt = await self.resolve_stt(stt_settings=stt_key_or_settings)
        else:
            stt = get_by_key_or_first(storage=await self.resolve_stts(), key=None)

        users_storage_key_or_settings = channel_settings.users_storage
        if isinstance(users_storage_key_or_settings, str):
            users_storage = get_by_key_or_first(
                storage=await self.resolve_users_storages(),
                key=users_storage_key_or_settings,
            )
            if users_storage is None:
                raise RuntimeError(f"Have no users storage with name \'{users_storage_key_or_settings}\'")
        elif isinstance(users_storage_key_or_settings, UsersStorageSettingsType):
            users_storage = get_users_storage(settings=users_storage_key_or_settings)
        else:
            users_storage = get_by_key_or_first(
                storage=await self.resolve_users_storages(),
                key=None,
            )

        syncer = await self.resolve_syncer()

        return get_channel(
            settings=channel_settings,
            sessions_storage=sessions_storage,
            agent=agent,
            stt=stt,
            channel_key=channel_key,
            syncer=syncer,
            users_storage=users_storage,
            resolver=self,
        )

    async def resolve_agents(self) -> dict[str, Agent]:
        if self._agents is None:
            self._agents = {
                key: await self.resolve_agent(agent_settings=agent_settings)
                for key, agent_settings in self._settings.agents.items()
            }
            for key, agent in self._agents.items():
                await self.resolve_subagents_for_agent(
                    agent=agent,
                    subagents_settings=self._settings.agents[key].subagents,
                )
        return self._agents

    async def resolve_agent(self, agent_settings: AgentSettings) -> Agent:
        model_settings = agent_settings.model
        if isinstance(model_settings, (str, NoneType)):
            model_settings = get_by_key_or_first(storage=self._settings.models, key=model_settings)
        if model_settings is None:
            raise RuntimeError(f"Have no model with name \'{agent_settings.model}\'")

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
        agent_toolkits = {}
        if agent_settings.toolkits is None:
            agent_toolkits = toolkits
        else:
            for toolkit_settings in agent_settings.toolkits:
                if toolkit_settings in toolkits:
                    agent_toolkits[toolkit_settings] = toolkits[toolkit_settings]
                    continue
                if isinstance(toolkit_settings, str):
                    toolkit_key = toolkit_settings
                else:
                    toolkit_key = toolkit_settings.name or toolkit_settings.path
                agent_toolkits[toolkit_key] = get_toolkit(
                    key=toolkit_key,
                    toolkit_settings_or_path=toolkit_settings,
                )

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

    async def resolve_subagents_for_agent(
            self,
            agent: Agent,
            subagents_settings: list[SubAgentSettings | str] | None,
    ):
        if subagents_settings is None:
            return

        subagent_toolkits = []
        for subagent_settings_or_key in subagents_settings:
            if isinstance(subagent_settings_or_key, str):
                if subagent_settings_or_key not in self._settings.agents:
                    raise ValueError(
                        f"Subagent '{subagent_settings_or_key}' not found in agents settings",
                    )
                agent_settings = self._settings.agents[subagent_settings_or_key]
                subagent_settings = SubAgentSettings(
                    name=agent_settings.identity.name,
                    description=agent_settings.identity.description,
                    agent=agent_settings.model_dump(),
                )
            elif isinstance(subagent_settings_or_key, SubAgentSettings):
                subagent_settings = subagent_settings_or_key
            else:
                raise ValueError(f"Invalid subagent settings type: {type(subagent_settings_or_key)}")

            if isinstance(subagent_settings.agent, str):
                subagent = self._agents.get(subagent_settings.agent)
            elif isinstance(subagent_settings.agent, dict):
                subagent = await self.resolve_agent(agent_settings=AgentSettings(**subagent_settings.agent))
            if subagent is None:
                raise ValueError(f"Agent for subagent '{subagent_settings.name}' not found")

            toolkit = SubAgentToolKit(
                settings=subagent_settings,
                agent=subagent,
            )
            subagent_toolkits.append(toolkit)

        agent.set_subagents_toolkits(subagent_toolkits)

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

    async def resolve_mcp(self, mcp_settings: dict[str, MCPSettings]) -> MultiServerMCPClient:
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

    async def resolve_syncer(self) -> SyncerInterface:
        if self._syncer is None:
            self._syncer = get_syncer(settings=self._settings.syncer)
        return self._syncer

    async def resolve_users_storages(self) -> dict[str, UsersStorageInterface]:
        if self._users_storages is None:
            self._users_storages = {
                key: get_users_storage(settings=users_storage_settings)
                for key, users_storage_settings in self._settings.users_storages.items()
            }
        return self._users_storages

    async def resolve_crons(self) -> dict[str, BaseCronTask]:
        if self._crons is None:
            self._crons = {}
            for key, cron_settings in self._settings.cron.items():
                if not cron_settings.enabled:
                    continue
                self._crons[key] = await get_cron_task(
                    key=key,
                    settings=cron_settings,
                    resolver=self,
                )
            self._crons["flush_to_memory"] = await get_cron_task(
                key="flush_to_memory",
                settings=CronTaskSettings(
                    path="microclaw.cron.tasks.flush_to_memory.FlushToMemoryCronTask",
                    cron="0 1 * * *",
                    enabled=True,
                ),
                resolver=self,
            )
            
            users_storages = await self.resolve_users_storages()
            for storage_key, users_storage in users_storages.items():
                async for user in users_storage.get_users():
                    user_crons = await users_storage.get_crons(user_id=user.id)
                    for cron_task in user_crons:
                        if not cron_task.enabled:
                            continue
                        cron_key = f"user_{user.id}_{cron_task.id}"
                        if cron_key in self._crons:
                            continue
                        cron_settings = CronTaskSettings(
                            path=cron_task.path,
                            cron=cron_task.cron,
                            enabled=cron_task.enabled,
                            args=cron_task.args,
                        )
                        self._crons[cron_key] = await get_cron_task(
                            key=cron_key,
                            settings=cron_settings,
                            resolver=self,
                        )
        return self._crons
