from typing import Any

from langgraph.types import interrupt

from microclaw.agents.settings import AgentSettings
from microclaw.dto import DecisionEnum
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context
from microclaw.toolkits.enums import PermissionModeEnum
from .settings import AgentConfigToolKitSettings


class AgentConfigToolKit(BaseToolKit[AgentConfigToolKitSettings]):
    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = [
        DiscoveryCapability.MODELS,
        DiscoveryCapability.TOOLKITS,
        DiscoveryCapability.SKILLS,
        DiscoveryCapability.AGENTS,
        DiscoveryCapability.MCP,
    ]

    async def _save_agent_settings(
        self,
        agent_settings: AgentSettings,
    ) -> None:
        """Validate via Pydantic and persist agent settings."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        # Re-validate to enforce all field constraints
        validated = AgentSettings.model_validate(agent_settings.model_dump(mode="json"))
        await ctx.current_user_accessor.update_agent_settings(
            validated.model_dump(mode="json")
        )

    @tool
    async def get_my_agent_config(self) -> str:
        """Get current personal agent configuration or default channel settings."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        if user is None or user.agent is None:
            return "Using default channel agent settings."
        return AgentSettings.model_validate(user.agent).model_dump_json(indent=2)

    @tool
    async def get_available_resources(self, option_type: str) -> list[dict[str, Any]]:
        """Get available resources: models, toolkits, skills, subagents, mcp."""
        ctx = get_toolkit_context()
        if ctx is None:
            raise RuntimeError("Not available outside channel context.")
        matches = {
            "models": ctx.all_models,
            "toolkits": ctx.all_toolkits,
            "skills": ctx.all_skills,
            "agents": ctx.all_agents,
            "subagents": ctx.all_agents,
            "mcp": ctx.all_mcp,
        }
        items = matches.get(option_type)
        if items is None:
            raise ValueError(
                f"Unknown option_type: {option_type}. Use models/toolkits/skills/agents/mcp."
            )
        return [item.model_dump(mode="json") for item in items.values()]

    @tool
    async def set_model(self, model_name: str) -> str:
        """Set the model for the agent."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        if ctx.all_models is None or model_name not in ctx.all_models:
            raise ValueError(f"Model '{model_name}' is not available.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model = model_name
        await self._save_agent_settings(agent_settings)
        return f"Model set to {model_name}."

    @tool
    async def set_identity(
        self,
        name: str | None = None,
        emoji: str | None = None,
        creature: str | None = None,
        vibe: str | None = None,
        description: str | None = None,
    ) -> str:
        """Update the agent's identity (name, emoji, creature, vibe, description)."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        if name is not None:
            agent_settings.identity.name = name
        if emoji is not None:
            agent_settings.identity.emoji = emoji
        if creature is not None:
            agent_settings.identity.creature = creature
        if vibe is not None:
            agent_settings.identity.vibe = vibe
        if description is not None:
            agent_settings.identity.description = description
        await self._save_agent_settings(agent_settings)
        return f"Identity updated: {agent_settings.identity.name} {agent_settings.identity.emoji}"

    @tool
    async def set_toolkits(self, toolkit_names: list[str]) -> str:
        """Set the list of active toolkits for the agent."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        if ctx.all_toolkits is None:
            raise RuntimeError("No toolkits available.")
        invalid = [t for t in toolkit_names if t not in ctx.all_toolkits]
        if invalid:
            raise ValueError(
                f"Invalid toolkits: {invalid}. Available: {list(ctx.all_toolkits.keys())}"
            )
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.toolkits = toolkit_names
        await self._save_agent_settings(agent_settings)
        return f"Active toolkits: {toolkit_names}"

    @tool
    async def set_skills(self, skill_names: list[str]) -> str:
        """Set the list of active skills for the agent."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        if ctx.all_skills is None:
            raise RuntimeError("No skills available.")
        invalid = [s for s in skill_names if s not in ctx.all_skills]
        if invalid:
            raise ValueError(
                f"Invalid skills: {invalid}. Available: {list(ctx.all_skills.keys())}"
            )
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.skills = skill_names
        await self._save_agent_settings(agent_settings)
        return f"Active skills: {skill_names}"

    @tool
    async def set_subagents(self, subagent_names: list[str]) -> str:
        """Set the list of active subagents for the agent."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        if ctx.all_agents is None:
            raise RuntimeError("No subagents available.")
        invalid = [a for a in subagent_names if a not in ctx.all_agents]
        if invalid:
            raise ValueError(
                f"Invalid subagents: {invalid}. Available: {list(ctx.all_agents.keys())}"
            )
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.subagents = subagent_names
        await self._save_agent_settings(agent_settings)
        return f"Active subagents: {subagent_names}"

    @tool
    async def set_mcp(self, mcp_names: list[str]) -> str:
        """Set the list of active MCP servers for the agent."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        if ctx.all_mcp is None:
            raise RuntimeError("No MCP servers available.")
        invalid = [m for m in mcp_names if m not in ctx.all_mcp]
        if invalid:
            raise ValueError(
                f"Invalid MCP servers: {invalid}. Available: {list(ctx.all_mcp.keys())}"
            )
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.mcp = mcp_names
        await self._save_agent_settings(agent_settings)
        return f"Active MCP servers: {mcp_names}"

    @tool
    async def set_temperature(self, temperature: float) -> str:
        """Set the temperature for the agent's model."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.temperature = temperature
        await self._save_agent_settings(agent_settings)
        return f"Temperature set to {temperature}."

    @tool
    async def set_max_tool_calls(self, max_tool_calls: int) -> str:
        """Set the maximum number of tool calls per request."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_tool_calls = max_tool_calls
        await self._save_agent_settings(agent_settings)
        return f"max_tool_calls set to {max_tool_calls}."

    @tool
    async def set_max_model_calls(self, max_model_calls: int) -> str:
        """Set the maximum number of model calls per request."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_model_calls = max_model_calls
        await self._save_agent_settings(agent_settings)
        return f"max_model_calls set to {max_model_calls}."

    @tool
    async def set_enable_summarization(self, enable_summarization: bool) -> str:
        """Enable or disable automatic dialog summarization."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.enable_summarization = enable_summarization
        await self._save_agent_settings(agent_settings)
        return f"Summarization {'enabled' if enable_summarization else 'disabled'}."

    @tool
    async def set_enable_memory_flush(self, enable_memory_flush: bool) -> str:
        """Enable or disable automatic memory flush."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.enable_memory_flush = enable_memory_flush
        await self._save_agent_settings(agent_settings)
        return f"Memory flush {'enabled' if enable_memory_flush else 'disabled'}."

    @tool
    async def set_max_memory_flush_tokens(self, max_memory_flush_tokens: int) -> str:
        """Set the maximum number of tokens for memory flush."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_memory_flush_tokens = max_memory_flush_tokens
        await self._save_agent_settings(agent_settings)
        return f"max_memory_flush_tokens set to {max_memory_flush_tokens}."

    @tool
    async def set_max_tool_output_chars(self, max_tool_output_chars: int) -> str:
        """Set the maximum number of characters for tool output."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_tool_output_chars = max_tool_output_chars
        await self._save_agent_settings(agent_settings)
        return f"max_tool_output_chars set to {max_tool_output_chars}."

    @tool
    async def set_model_max_retries(self, model_max_retries: int) -> str:
        """Set the maximum number of model retries."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model_max_retries = model_max_retries
        await self._save_agent_settings(agent_settings)
        return f"model_max_retries set to {model_max_retries}."

    @tool
    async def set_model_retry_backoff_factor(self, model_retry_backoff_factor: float) -> str:
        """Set the backoff factor for model retries."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model_retry_backoff_factor = model_retry_backoff_factor
        await self._save_agent_settings(agent_settings)
        return f"model_retry_backoff_factor set to {model_retry_backoff_factor}."

    @tool
    async def set_model_retry_initial_delay(self, model_retry_initial_delay: float) -> str:
        """Set the initial delay for model retries."""
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model_retry_initial_delay = model_retry_initial_delay
        await self._save_agent_settings(agent_settings)
        return f"model_retry_initial_delay set to {model_retry_initial_delay}."

    @tool
    async def reset_agent_config(self) -> str:
        """Reset agent configuration to channel defaults."""
        if self._settings.reset_mode is PermissionModeEnum.DENY:
            raise PermissionError("Reset is not allowed")
        if self._settings.reset_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": "Reset agent configuration to defaults?"})
            if decision == DecisionEnum.REJECT.value:
                from microclaw.toolkits.exceptions import UserDeniedAction
                raise UserDeniedAction()
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        await ctx.current_user_accessor.update_agent_settings(None)
        return "Agent configuration reset to channel defaults."
