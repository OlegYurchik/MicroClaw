from typing import Any
import uuid

from .settings import MCPManagerToolKitSettings
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import interrupt

from microclaw.agents.settings import (
    AgentSettings,
    MCPLocalSettings,
    MCPRemoteSettings,
    MCPSettings,
)
from microclaw.dto import DecisionEnum
from microclaw.toolkits.base import AgentSettingsMixin, BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction


class MCPManagerToolKit(BaseToolKit[MCPManagerToolKitSettings], AgentSettingsMixin):
    """Tools for managing per-user MCP servers.

    All tools that read or mutate a user's agent configuration accept an optional
    ``user_id`` parameter.  If *omitted*, the operation acts on the **current**
    user.  If provided, the toolkit targets the specified user; this requires the
    ``ALL_USERS`` capability (writable) to be granted to the toolkit context.
    """

    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = [DiscoveryCapability.MCP]

    @tool
    async def list_global_mcp(self) -> list[dict[str, Any]]:
        """List global MCP servers from channel configuration."""
        ctx = self._require_context()
        if ctx.all_mcp is None:
            return []
        return [
            {"name": k, "description": v.description} for k, v in ctx.all_mcp.items()
        ]

    @tool
    async def list_my_mcp(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List the MCP servers in a user's agent configuration.

        Args:
            user_id: UUID of the user to inspect.  If omitted, the current
                user's configuration is returned.
        """
        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)
        if not agent_settings.mcp:
            return []
        result = []
        for item in agent_settings.mcp:
            if isinstance(item, str):
                result.append({"name": item, "type": "reference"})
            else:
                name = item.name or item.url or item.command
                result.append(
                    {
                        "name": name,
                        "type": (
                            "remote"
                            if isinstance(item, MCPRemoteSettings)
                            else "local"
                        ),
                        "description": item.description,
                    }
                )
        return result

    @tool
    async def add_custom_mcp(
        self, config: MCPSettings, user_id: str | None = None
    ) -> str:
        """Add a custom MCP server (HTTP/WebSocket or stdio) to a user's agent.

        Args:
            config: ``MCPRemoteSettings`` or ``MCPLocalSettings`` configuration.
            user_id: UUID of the target user.  If omitted, the server is added
                to the **current** user's configuration.
        """
        if self._arguments.add_mode is PermissionModeEnum.DENY:
            raise PermissionError("Adding MCP servers is not allowed")
        if self._arguments.source_mode in (SourceModeEnum.GLOBAL, SourceModeEnum.EMPTY):
            raise PermissionError(
                "Adding custom MCP servers is not allowed. "
                "No custom sources configured."
            )
        if user_id is not None:
            await self._require_cross_user_write()

        if self._arguments.add_mode is PermissionModeEnum.REQUEST:
            decision = interrupt(
                {"description": f"Add custom MCP server '{config.name}'?"}
            )
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)
        mcp_list = list(agent_settings.mcp or [])

        existing_names = self._get_existing_mcp_names(mcp_list)
        if config.name in existing_names:
            raise ValueError(f"MCP server '{config.name}' already exists.")

        mcp_list.append(config)
        agent_settings.mcp = mcp_list
        await self._save_agent_settings(agent_settings, target_id)
        return f"MCP server '{config.name}' added."

    @tool
    async def enable_mcp(self, name: str, user_id: str | None = None) -> str:
        """Enable a global MCP server (from channel configuration) for a user.

        Args:
            name: Name of the global MCP server as defined in ``config.yaml``.
            user_id: UUID of the target user.  If omitted, the server is enabled
                for the **current** user.
        """
        if self._arguments.add_mode is PermissionModeEnum.DENY:
            raise PermissionError("Enabling MCP servers is not allowed")
        if self._arguments.source_mode in (
            SourceModeEnum.MARKETPLACE,
            SourceModeEnum.EMPTY,
        ):
            raise PermissionError(
                "Enabling global MCP servers is not allowed. "
                "No global sources configured."
            )
        if user_id is not None:
            await self._require_cross_user_write()

        if self._arguments.add_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Enable global MCP server '{name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        ctx = self._require_context()
        if ctx.all_mcp is None or name not in ctx.all_mcp:
            available = list(ctx.all_mcp.keys()) if ctx.all_mcp else []
            raise ValueError(
                f"Global MCP server '{name}' not found. Available: {available}"
            )

        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)
        mcp_list = list(agent_settings.mcp or [])

        existing_names = self._get_existing_mcp_names(mcp_list)
        if name in existing_names:
            raise ValueError(f"MCP server '{name}' already exists.")

        mcp_list.append(name)
        agent_settings.mcp = mcp_list
        await self._save_agent_settings(agent_settings, target_id)
        return f"Global MCP server '{name}' enabled."

    @tool
    async def remove_mcp(self, name: str, user_id: str | None = None) -> str:
        """Remove an MCP server from a user's agent configuration.

        Global servers configured in ``config.yaml`` cannot be removed.

        Args:
            name: Name of the MCP server to remove.
            user_id: UUID of the target user.  If omitted, the server is removed
                from the **current** user's configuration.
        """
        if self._arguments.remove_mode is PermissionModeEnum.DENY:
            raise PermissionError("Removing MCP servers is not allowed")
        if user_id is not None:
            await self._require_cross_user_write()

        if self._arguments.remove_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Remove MCP server '{name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        target_id = await self._resolve_target_user_id(user_id)
        ctx = self._require_context()
        agent_settings = await self._load_agent_settings(target_id)
        if not agent_settings.mcp:
            if ctx.all_mcp and name in ctx.all_mcp:
                raise PermissionError(
                    f"MCP server '{name}' is global and cannot be removed."
                )
            raise ValueError(f"MCP server '{name}' not found.")

        per_user_names = set()
        for item in agent_settings.mcp:
            item_name = (
                item
                if isinstance(item, str)
                else (item.name or item.url or item.command)
            )
            per_user_names.add(item_name)

        if name not in per_user_names:
            if ctx.all_mcp and name in ctx.all_mcp:
                raise PermissionError(
                    f"MCP server '{name}' is global and cannot be removed."
                )
            raise ValueError(f"MCP server '{name}' not found.")

        new_mcp = [
            item
            for item in agent_settings.mcp
            if (
                item
                if isinstance(item, str)
                else (item.name or item.url or item.command)
            )
            != name
        ]
        agent_settings.mcp = new_mcp
        await self._save_agent_settings(agent_settings, target_id)
        return f"MCP server '{name}' removed."

    @tool
    async def test_mcp(self, name: str, user_id: str | None = None) -> str:
        """Test the connection to an MCP server in a user's configuration.

        Args:
            name: Name of the MCP server to test.
            user_id: UUID of the user whose configuration to inspect.  If
                omitted, the **current** user's configuration is checked.
        """
        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)

        mcp_settings = None
        for item in agent_settings.mcp or []:
            if isinstance(item, str):
                ctx = self._require_context()
                if item == name and (ctx.all_mcp and item in ctx.all_mcp):
                    raise ValueError(
                        f"MCP server '{name}' is a reference to a global server. "
                        "Connection test not supported for references."
                    )
                continue
            item_name = item.name or item.url or item.command
            if item_name == name:
                mcp_settings = item
                break

        if mcp_settings is None:
            ctx = self._require_context()
            if name in (ctx.all_mcp or {}):
                raise ValueError(
                    f"MCP server '{name}' is a global server. "
                    "Connection test not supported for global references."
                )
            raise ValueError(f"MCP server '{name}' not found.")

        servers = self._build_mcp_servers(mcp_settings)
        if not servers:
            raise ValueError(f"Could not build server config for '{name}'.")

        try:
            async with MultiServerMCPClient(servers) as client:
                tools = await client.get_tools()
                return (
                    f"MCP server '{name}' connected successfully. "
                    f"Available tools: {len(tools)}."
                )
        except Exception as exc:
            raise RuntimeError(
                f"MCP server '{name}' connection failed: {exc}"
            ) from exc

    async def _resolve_target_user_id(
        self, user_id: str | None
    ) -> uuid.UUID | None:
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
    ) -> AgentSettings:
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
        agent_settings: AgentSettings,
        target_user_id: uuid.UUID | None = None,
    ) -> None:
        ctx = self._require_context()

        def _merge_with_channel(base: AgentSettings) -> AgentSettings:
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

    def _get_existing_mcp_names(self, mcp_list: list) -> set[str]:
        names = set()
        for item in mcp_list:
            if isinstance(item, str):
                names.add(item)
            else:
                names.add(item.name or item.url or item.command)
        return names

    def _build_mcp_servers(
        self, mcp_settings: MCPSettings
    ) -> dict[str, dict[str, Any]]:
        servers: dict[str, dict[str, Any]] = {}
        if isinstance(mcp_settings, MCPRemoteSettings):
            server_name = mcp_settings.name or mcp_settings.url
            mcp_data: dict[str, Any] = {}
            if mcp_settings.url.startswith("http"):
                mcp_data["transport"] = "http"
            elif mcp_settings.url.startswith("ws"):
                mcp_data["transport"] = "ws"
            else:
                return {}
            mcp_data["url"] = mcp_settings.url
            mcp_data["headers"] = mcp_settings.headers or {}
            servers[server_name] = mcp_data
        elif isinstance(mcp_settings, MCPLocalSettings):
            server_name = mcp_settings.name or " ".join(
                (mcp_settings.command, *mcp_settings.args)
            )
            mcp_data = {
                "transport": "stdio",
                "command": mcp_settings.command,
                "args": mcp_settings.args or [],
            }
            mcp_data["env"] = mcp_settings.env or {}
            servers[server_name] = mcp_data
        return servers

