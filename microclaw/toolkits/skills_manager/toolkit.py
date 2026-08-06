import pathlib
import uuid
from typing import Any

import skilly
from langgraph.types import interrupt
from skilly.skills import discover_github_skills
from skilly.skillsmp.client import SkillsMp

from microclaw.agents.settings import AgentSettings
from microclaw.dto import DecisionEnum
from microclaw.skills import SkillSettings
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction

from .settings import SkillsManagerToolKitSettings


class SkillsManagerToolKit(BaseToolKit[SkillsManagerToolKitSettings]):
    """Tools for managing skills marketplace, installation, and per-user activation.

    All tools that read or mutate a user's agent configuration accept an optional
    ``user_id`` parameter.  If *omitted*, the operation acts on the **current**
    user.  If provided, the toolkit targets the specified user; this requires the
    ``ALL_USERS`` capability (writable) to be granted to the toolkit context.
    """

    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = [DiscoveryCapability.SKILLS]

    @tool
    async def search_skills(self, query: str) -> list[dict[str, Any]]:
        """Search for skills in the Skills Marketplace."""
        from loguru import logger
        results = []
        try:
            mp_result = SkillsMp().search(query)
            for skill in mp_result.data.skills:
                results.append(
                    {
                        "name": skill.name,
                        "description": skill.description,
                        "author": skill.author,
                        "stars": skill.stars,
                        "source": "marketplace",
                        "github_url": skill.github_url,
                    }
                )
        except Exception as exc:
            logger.warning("Skills marketplace search failed: {}", exc)
        return results

    @tool
    async def list_installed_skills(
        self, user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List all skills installed in a user's skills directory.

        Args:
            user_id: UUID of the user to inspect.  If omitted, the current
                user's directory is listed.
        """
        target_id = await self._resolve_target_user_id(user_id)
        repo = await self._get_repo(target_id)
        installed = repo.list()
        return [
            {
                "name": skill.name,
                "path": str(skill.path),
                "description": skill.description,
            }
            for skill in installed
        ]

    @tool
    async def get_skill_info(
        self, name: str, user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get README and metadata for an installed skill.

        Args:
            name: Name of the installed skill.
            user_id: UUID of the user whose installation to inspect.
                If omitted, the **current** user's installation is used.

        Returns:
            Skill metadata or None if the skill is not installed.
        """
        target_id = await self._resolve_target_user_id(user_id)
        repo = await self._get_repo(target_id)
        installed = repo.find(name)
        if installed is None:
            return None
        info: dict[str, Any] = {
            "name": installed.name,
            "description": installed.description,
            "path": str(installed.path),
        }
        if installed.content:
            info["readme"] = installed.content
        else:
            info["readme"] = None
        return info

    @tool
    async def install_skill(self, name: str, user_id: str | None = None) -> str:
        """Install a skill from the Skills Marketplace for a user.

        Args:
            name: Name (or directory name) of the skill to install.
            user_id: UUID of the target user.  If omitted, the skill is
                installed for the **current** user.
        """
        if self._settings.install_mode is PermissionModeEnum.DENY:
            raise PermissionError("Skill installation is not allowed")
        if self._settings.source_mode in (SourceModeEnum.GLOBAL, SourceModeEnum.EMPTY):
            raise PermissionError(
                "Installing skills from marketplace is not allowed. "
                "No marketplace sources configured."
            )
        if user_id is not None:
            await self._require_cross_user_write()

        if self._settings.install_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Install skill '{name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        target_id = await self._resolve_target_user_id(user_id)
        repo = await self._get_repo(target_id)
        if repo.find(name) is not None:
            raise ValueError(f"Skill '{name}' is already installed.")

        try:
            mp_result = SkillsMp().search(name)
            for smp_skill in mp_result.data.skills:
                if smp_skill.name == name:
                    discovered = discover_github_skills(None, smp_skill.github_url)
                    for d in discovered:
                        if d.directory_name == name or d.name == name:
                            repo.install(d, skill_name=name)
                            return f"Skill '{name}' installed from marketplace."
        except Exception as exc:
            raise RuntimeError(f"Failed to install skill '{name}': {exc}") from exc

        raise ValueError(f"Skill '{name}' not found in marketplace.")

    @tool
    async def remove_skill(self, name: str, user_id: str | None = None) -> str:
        """Remove an installed skill from a user's skills directory.

        Args:
            name: Name of the skill to remove.
            user_id: UUID of the target user.  If omitted, the skill is
                removed from the **current** user.
        """
        if self._settings.remove_mode is PermissionModeEnum.DENY:
            raise PermissionError("Skill removal is not allowed")
        if user_id is not None:
            await self._require_cross_user_write()

        if self._settings.remove_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Remove skill '{name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        target_id = await self._resolve_target_user_id(user_id)
        repo = await self._get_repo(target_id)
        installed = repo.find(name)
        if installed is None:
            raise ValueError(f"Skill '{name}' is not installed.")

        repo.remove(name)
        return f"Skill '{name}' removed."

    @tool
    async def update_skill(self, name: str, user_id: str | None = None) -> str:
        """Reinstall / update a skill from the Skills Marketplace for a user.

        Args:
            name: Name of the installed skill to update.
            user_id: UUID of the target user.  If omitted, the skill is
                updated for the **current** user.
        """
        if self._settings.update_mode is PermissionModeEnum.DENY:
            raise PermissionError("Skill update is not allowed")
        if self._settings.source_mode in (SourceModeEnum.GLOBAL, SourceModeEnum.EMPTY):
            raise PermissionError(
                "Updating skills from marketplace is not allowed. "
                "No marketplace sources configured."
            )
        if user_id is not None:
            await self._require_cross_user_write()

        if self._settings.update_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Update skill '{name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        target_id = await self._resolve_target_user_id(user_id)
        repo = await self._get_repo(target_id)
        installed = repo.find(name)
        if installed is None:
            raise ValueError(
                f"Skill '{name}' is not installed. Use install_skill instead."
            )

        mp_result = SkillsMp().search(name)
        for smp_skill in mp_result.data.skills:
            if smp_skill.name == name:
                discovered = discover_github_skills(None, smp_skill.github_url)
                for d in discovered:
                    if d.directory_name == name or d.name == name:
                        repo.remove(name)
                        repo.install(d, skill_name=name)
                        return f"Skill '{name}' updated."

        raise ValueError(f"Skill '{name}' not found in marketplace for update.")

    @tool
    async def enable_skill(self, name: str, user_id: str | None = None) -> str:
        """Enable a global skill (from channel configuration) for a user.

        Args:
            name: Name of the global skill as defined in ``config.yaml``.
            user_id: UUID of the target user.  If omitted, the skill is enabled
                for the **current** user.
        """
        if self._settings.enable_mode is PermissionModeEnum.DENY:
            raise PermissionError("Enabling skills is not allowed")
        if self._settings.source_mode in (
            SourceModeEnum.MARKETPLACE,
            SourceModeEnum.EMPTY,
        ):
            raise PermissionError(
                "Enabling global skills is not allowed. "
                "No global sources configured."
            )
        if user_id is not None:
            await self._require_cross_user_write()

        if self._settings.enable_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": f"Enable skill '{name}'?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        ctx = self._require_context()
        if ctx.all_skills is None or name not in ctx.all_skills:
            available = list(ctx.all_skills.keys()) if ctx.all_skills else []
            raise ValueError(
                f"Global skill '{name}' not found. Available: {available}"
            )

        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)
        current_skills = list(agent_settings.skills or [])

        skill_names = [
            s.name if isinstance(s, SkillSettings) else s for s in current_skills
        ]
        if name in skill_names:
            raise ValueError(f"Skill '{name}' is already active.")

        current_skills.append(name)
        agent_settings.skills = current_skills
        await self._save_agent_settings(agent_settings, target_id)
        return f"Global skill '{name}' enabled."

    @tool
    async def list_my_skills(self, user_id: str | None = None) -> list[str]:
        """List active skills in a user's agent configuration.

        Args:
            user_id: UUID of the user to inspect.  If omitted, the current
                user's active skills are returned.
        """
        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)
        if not agent_settings.skills:
            return []
        return [
            s.name if isinstance(s, SkillSettings) else s for s in agent_settings.skills
        ]

    @tool
    async def add_skill_to_my_agent(
        self, skill: str | SkillSettings, user_id: str | None = None
    ) -> str:
        """Add an installed skill (by name) or a custom skill config to a user's agent.

        Args:
            skill: Skill name (if already installed) or a ``SkillSettings`` config.
            user_id: UUID of the target user.  If omitted, the skill is added
                to the **current** user.
        """
        if self._settings.enable_mode is PermissionModeEnum.DENY:
            raise PermissionError("Adding skills to agent is not allowed")
        if self._settings.source_mode is SourceModeEnum.EMPTY:
            raise PermissionError(
                "Adding skills is not allowed. No sources configured."
            )
        if (
            self._settings.source_mode is SourceModeEnum.GLOBAL
            and isinstance(skill, SkillSettings)
        ):
            raise PermissionError(
                "Adding custom skill configurations is not allowed in global-only mode."
            )
        if user_id is not None:
            await self._require_cross_user_write()

        if self._settings.enable_mode is PermissionModeEnum.REQUEST:
            name_preview = skill if isinstance(skill, str) else skill.name
            decision = interrupt(
                {"description": f"Add skill '{name_preview}' to agent?"}
            )
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)
        current_skills = list(agent_settings.skills or [])

        name = skill if isinstance(skill, str) else skill.name

        skill_names = [
            s.name if isinstance(s, SkillSettings) else s for s in current_skills
        ]
        if name in skill_names:
            raise ValueError(f"Skill '{name}' is already active.")

        if isinstance(skill, str):
            repo = await self._get_repo(target_id)
            if repo.find(name) is None:
                raise ValueError(f"Skill '{name}' is not installed. Install it first.")
            current_skills.append(skill)
        else:
            current_skills.append(skill)

        agent_settings.skills = current_skills
        await self._save_agent_settings(agent_settings, target_id)
        return f"Skill '{name}' added to agent."

    @tool
    async def remove_skill_from_my_agent(
        self, name: str, user_id: str | None = None
    ) -> str:
        """Remove a skill from a user's active skills.

        Args:
            name: Name of the skill to remove.
            user_id: UUID of the target user.  If omitted, the skill is
                removed from the **current** user.
        """
        if self._settings.remove_mode is PermissionModeEnum.DENY:
            raise PermissionError("Removing skills from agent is not allowed")
        if user_id is not None:
            await self._require_cross_user_write()

        if self._settings.remove_mode is PermissionModeEnum.REQUEST:
            decision = interrupt(
                {"description": f"Remove skill '{name}' from agent?"}
            )
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        target_id = await self._resolve_target_user_id(user_id)
        agent_settings = await self._load_agent_settings(target_id)
        if not agent_settings.skills:
            raise ValueError(f"Skill '{name}' is not active.")

        new_skills = [
            s
            for s in agent_settings.skills
            if (s.name if isinstance(s, SkillSettings) else s) != name
        ]
        if len(new_skills) == len(agent_settings.skills):
            raise ValueError(f"Skill '{name}' is not active.")

        agent_settings.skills = new_skills
        await self._save_agent_settings(agent_settings, target_id)
        return f"Skill '{name}' removed from agent."

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

    async def _get_repo(
        self, target_user_id: uuid.UUID | None = None
    ) -> skilly.SkillRepository:
        ctx = self._require_context()
        if target_user_id is None:
            user = await ctx.current_user_accessor.get()
        else:
            if ctx.all_users_accessor is None:
                raise PermissionError("Cross-user access not granted")
            user = await ctx.all_users_accessor.get_by_id(target_user_id)
        if user is None:
            raise RuntimeError("User not found")
        user_dir = pathlib.Path(self._settings.skills_directory) / str(user.id)
        user_dir.mkdir(parents=True, exist_ok=True)
        return skilly.SkillRepository(directory=user_dir.resolve())

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

