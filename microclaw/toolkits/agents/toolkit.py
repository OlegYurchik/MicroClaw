from typing import Any

from .settings import AgentsToolKitSettings
from langgraph.types import interrupt

from microclaw.agents.settings import AgentSettings
from microclaw.dto import DecisionEnum
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction


class AgentsToolKit(BaseToolKit[AgentsToolKitSettings]):
    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = [
        DiscoveryCapability.MODELS,
        DiscoveryCapability.TOOLKITS,
        DiscoveryCapability.SKILLS,
        DiscoveryCapability.AGENTS,
        DiscoveryCapability.MCP,
    ]

    @tool
    async def get_agent_settings(self) -> str:
        """Get current personal agent configuration or default channel settings."""
        user = await self._require_context().current_user_accessor.get()
        if user is None or user.agent is None:
            return "Using default channel agent settings."
        return AgentSettings.model_validate(user.agent).model_dump_json(indent=2)

    @tool
    async def get_available_global_resources(self, option_type: str) -> list[dict[str, Any]]:
        """Get available global resources: models, toolkits, skills, subagents, mcp."""
        ctx = self._require_context()
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
    async def set_agent_model(self, model_name: str) -> str:
        """Set the model for the agent by selecting one of the globally available models."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting agent model is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set model to '{model_name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        ctx = self._require_context()
        if ctx.all_models is None or model_name not in ctx.all_models:
            raise ValueError(f"Model '{model_name}' is not available.")
        agent_settings = await self._load_agent_settings()
        agent_settings.model = model_name
        await self._save_agent_settings(agent_settings)
        return f"Model set to {model_name}."

    @tool
    async def set_agent_identity(
        self,
        name: str | None = None,
        emoji: str | None = None,
        creature: str | None = None,
        vibe: str | None = None,
        description: str | None = None,
    ) -> str:
        """Update the agent's identity (name, emoji, creature, vibe, description)."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting agent identity is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": "Update agent identity?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
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
    async def set_agent_subagents(self, subagent_names: list[str]) -> str:
        """Set the list of active subagents for the agent."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting agent subagents is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set subagents to {subagent_names}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        ctx = self._require_context()
        if ctx.all_agents is None:
            raise RuntimeError("No subagents available.")
        invalid = [a for a in subagent_names if a not in ctx.all_agents]
        if invalid:
            raise ValueError(
                f"Invalid subagents: {invalid}. Available: {list(ctx.all_agents.keys())}"
            )
        agent_settings = await self._load_agent_settings()
        agent_settings.subagents = subagent_names
        await self._save_agent_settings(agent_settings)
        return f"Active subagents: {subagent_names}"

    @tool
    async def list_my_subagents(self) -> list[dict[str, Any]]:
        """List active subagents for the current agent (global references + custom configs)."""
        agent_settings = await self._load_agent_settings()
        result = []
        for item in agent_settings.subagents:
            if isinstance(item, str):
                result.append({"name": item, "type": "global"})
            else:
                result.append(
                    {
                        "name": item.identity.name,
                        "type": "custom",
                        "model": item.model if isinstance(item.model, str) else None,
                        "identity": item.identity.model_dump(mode="json"),
                    }
                )
        return result

    @tool
    async def add_custom_subagent(self, config: AgentSettings) -> str:
        """Add a custom subagent configuration to the agent.

        The subagent model must be a globally available model name.
        """
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Adding custom subagents is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt(
                {"description": f"Add custom subagent '{config.identity.name}'?"}
            )
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        ctx = self._require_context()
        if ctx.all_models is None:
            raise RuntimeError("No global models available. Cannot create custom subagents.")

        if isinstance(config.model, str):
            if config.model not in ctx.all_models:
                raise ValueError(f"Model '{config.model}' is not available.")
        elif config.model is not None:
            raise ValueError(
                "Custom model configurations are not allowed. Use a global model name."
            )

        agent_settings = await self._load_agent_settings()
        existing_names = self._get_subagent_names(agent_settings.subagents)
        name = config.identity.name
        if name in existing_names:
            raise ValueError(f"Subagent '{name}' is already active.")

        agent_settings.subagents = list(agent_settings.subagents) + [config]
        await self._save_agent_settings(agent_settings)
        return f"Custom subagent '{name}' added."

    @tool
    async def remove_subagent(self, name: str) -> str:
        """Remove a subagent from the active list by name."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Removing subagents is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Remove subagent '{name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        agent_settings = await self._load_agent_settings()
        existing_names = self._get_subagent_names(agent_settings.subagents)
        if name not in existing_names:
            raise ValueError(f"Subagent '{name}' is not active.")

        new_subagents = [
            item
            for item in agent_settings.subagents
            if (item if isinstance(item, str) else item.identity.name) != name
        ]
        agent_settings.subagents = new_subagents
        await self._save_agent_settings(agent_settings)
        return f"Subagent '{name}' removed."

    def _get_subagent_names(self, subagents: list[str | AgentSettings]) -> set[str]:
        names = set()
        for item in subagents:
            if isinstance(item, str):
                names.add(item)
            else:
                names.add(item.identity.name)
        return names

    @tool
    async def set_agent_temperature(self, temperature: float) -> str:
        """Set the temperature for the agent's model."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting agent temperature is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set temperature to {temperature}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.temperature = temperature
        await self._save_agent_settings(agent_settings)
        return f"Temperature set to {temperature}."

    @tool
    async def set_agent_max_tool_calls(self, max_tool_calls: int) -> str:
        """Set the maximum number of tool calls per request."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting max_tool_calls is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set max_tool_calls to {max_tool_calls}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.max_tool_calls = max_tool_calls
        await self._save_agent_settings(agent_settings)
        return f"max_tool_calls set to {max_tool_calls}."

    @tool
    async def set_agent_max_model_calls(self, max_model_calls: int) -> str:
        """Set the maximum number of model calls per request."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting max_model_calls is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set max_model_calls to {max_model_calls}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.max_model_calls = max_model_calls
        await self._save_agent_settings(agent_settings)
        return f"max_model_calls set to {max_model_calls}."

    @tool
    async def set_agent_summarization(self, enable_summarization: bool) -> str:
        """Enable or disable automatic dialog summarization."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting summarization is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set summarization to {enable_summarization}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.enable_summarization = enable_summarization
        await self._save_agent_settings(agent_settings)
        return f"Summarization {'enabled' if enable_summarization else 'disabled'}."

    @tool
    async def set_agent_memory_flush(self, enable_memory_flush: bool) -> str:
        """Enable or disable automatic memory flush."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting memory flush is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set memory flush to {enable_memory_flush}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.enable_memory_flush = enable_memory_flush
        await self._save_agent_settings(agent_settings)
        return f"Memory flush {'enabled' if enable_memory_flush else 'disabled'}."

    @tool
    async def set_agent_max_memory_flush_tokens(
        self, max_memory_flush_tokens: int
    ) -> str:
        """Set the maximum number of tokens for memory flush."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting max_memory_flush_tokens is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set max_memory_flush_tokens to {max_memory_flush_tokens}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.max_memory_flush_tokens = max_memory_flush_tokens
        await self._save_agent_settings(agent_settings)
        return f"max_memory_flush_tokens set to {max_memory_flush_tokens}."

    @tool
    async def set_agent_max_tool_output_chars(self, max_tool_output_chars: int) -> str:
        """Set the maximum number of characters for tool output."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting max_tool_output_chars is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set max_tool_output_chars to {max_tool_output_chars}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.max_tool_output_chars = max_tool_output_chars
        await self._save_agent_settings(agent_settings)
        return f"max_tool_output_chars set to {max_tool_output_chars}."

    @tool
    async def set_agent_model_max_retries(self, model_max_retries: int) -> str:
        """Set the maximum number of model retries."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting model_max_retries is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set model_max_retries to {model_max_retries}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.model_max_retries = model_max_retries
        await self._save_agent_settings(agent_settings)
        return f"model_max_retries set to {model_max_retries}."

    @tool
    async def set_agent_model_retry_backoff_factor(
        self, model_retry_backoff_factor: float
    ) -> str:
        """Set the backoff factor for model retries."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting model_retry_backoff_factor is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set model_retry_backoff_factor to {model_retry_backoff_factor}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.model_retry_backoff_factor = model_retry_backoff_factor
        await self._save_agent_settings(agent_settings)
        return f"model_retry_backoff_factor set to {model_retry_backoff_factor}."

    @tool
    async def set_agent_model_retry_initial_delay(
        self, model_retry_initial_delay: float
    ) -> str:
        """Set the initial delay for model retries."""
        if self._arguments.set_mode is PermissionModeEnum.DENY:
            raise PermissionError("Setting model_retry_initial_delay is not allowed")
        if self._arguments.set_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Set model_retry_initial_delay to {model_retry_initial_delay}?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        agent_settings = await self._load_agent_settings()
        agent_settings.model_retry_initial_delay = model_retry_initial_delay
        await self._save_agent_settings(agent_settings)
        return f"model_retry_initial_delay set to {model_retry_initial_delay}."

    @tool
    async def reset_agent_settings(self) -> str:
        """Reset agent configuration to channel defaults."""
        if self._arguments.reset_mode is PermissionModeEnum.DENY:
            raise PermissionError("Reset is not allowed")
        if self._arguments.reset_mode is PermissionModeEnum.REQUEST:
            decision = interrupt(
                {"description": "Reset agent configuration to defaults?"}
            )
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()
        await self._require_context().current_user_accessor.update_agent_settings(None)
        return "Agent configuration reset to channel defaults."

    async def _load_agent_settings(self) -> AgentSettings:
        """Load current user's AgentSettings (or defaults)."""
        ctx = self._require_context()
        user = await ctx.current_user_accessor.get()
        if user.agent:
            return AgentSettings.model_validate(user.agent)
        if ctx.channel_agent_settings:
            return AgentSettings.model_validate(ctx.channel_agent_settings)
        return AgentSettings()

    async def _save_agent_settings(
        self,
        agent_settings: AgentSettings,
    ) -> None:
        """Validate via Pydantic and persist agent settings."""
        ctx = self._require_context()
        user = await ctx.current_user_accessor.get()
        if ctx.channel_agent_settings and user.agent is None:
            # First write — copy channel agent and apply overrides
            merged = AgentSettings.model_validate(ctx.channel_agent_settings)
            for field_name in AgentSettings.model_fields:
                override_value = getattr(agent_settings, field_name)
                if override_value is not None:
                    setattr(merged, field_name, override_value)
            agent_settings = merged
        validated = AgentSettings.model_validate(agent_settings.model_dump(mode="json"))
        await ctx.current_user_accessor.update_agent_settings(validated)

