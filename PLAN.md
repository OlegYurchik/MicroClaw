# План реализации: AgentConfig ToolKit

## Цель

Позволить пользователю самостоятельно настраивать персональные параметры своего агента (`AgentSettings`) через естественный язык, без редактирования YAML. Настройки хранятся в `User.agent` (per-user override) и применяются через механизм `BaseChannel.get_agent_for_user()`.

---

## Выполненные шаги

- [x] **1.1** — Создать capability enums
- [x] **1.2** — Добавить capabilities в `BaseToolKit`
- [x] **1.3** — Создать discovery DTO
- [x] **1.4** — Создать пакет `microclaw/toolkits/accessors/`
- [x] **1.5** — Создать `ToolkitExecutionContext`
- [x] **1.6** — Обновить `BaseChannel`
- [x] **1.7** — Обновить каналы (telegram, cli, vk)
- [x] **2.1** — Мигрировать `CronToolKit`
- [x] **2.2** — Мигрировать `SessionsToolKit`
- [x] **2.3** — Добавить capabilities во все остальные тулкиты
- [x] **3.1** — Настройки `AgentConfigToolKit` (`microclaw/toolkits/agent_config/settings.py`)
- [x] **3.2** — Реализация `AgentConfigToolKit` (`microclaw/toolkits/agent_config/toolkit.py`)
- [x] **3.3** — `__init__.py` для `agent_config`
- [x] **4.1** — Тесты контекста и accessors
- [x] **5.1** — Добавить тулкит в конфигурацию
- [x] **5.2** — Ручная проверка (pytest + импорт)

---

---

## Фаза 2: Миграция тулкитов

---

## Фаза 1: Инфраструктура

### Шаг 1.2: Добавить capabilities в `BaseToolKit`

**Файл:** `microclaw/toolkits/capabilities.py` (новый)

```python
import enum


class ToolKitCapability(str, enum.Enum):
    """Access to runtime users and sessions."""
    CURRENT_USER = "current_user"
    ALL_USERS = "all_users"
    CURRENT_SESSION = "current_session"
    ALL_SESSIONS = "all_sessions"


class DiscoveryCapability(str, enum.Enum):
    """Read-only access to globally available resource names and descriptions."""
    MODELS = "models"
    TOOLKITS = "toolkits"
    SKILLS = "skills"
    AGENTS = "agents"
    MCP = "mcp"
```

---

### Шаг 1.2: Добавить capabilities в `BaseToolKit`

**Файл:** `microclaw/toolkits/base.py`

```python
from .capabilities import ToolKitCapability, DiscoveryCapability


class BaseToolKit(Generic[SettingsType]):
    required_capabilities: list[ToolKitCapability] = []
    write_capabilities: list[ToolKitCapability] = []
    discovery_capabilities: list[DiscoveryCapability] = []
    # ...
```

---

### Шаг 1.3: Создать discovery DTO

**Файл:** `microclaw/toolkits/dto.py` (новый)

```python
from pydantic import BaseModel


class DiscoveryInfo(BaseModel):
    """Minimal name + description for any discoverable entity."""

    name: str
    description: str | None = None
```

---

### Шаг 1.4: Создать пакет `microclaw/toolkits/accessors/`

**Файл:** `microclaw/toolkits/accessors/__init__.py` (новый)

```python
from .user import CurrentUserAccessor, AllUsersAccessor, UserSessionsAccessor
from .session import CurrentSessionAccessor, AllSessionsAccessor

__all__ = (
    "CurrentUserAccessor",
    "AllUsersAccessor",
    "UserSessionsAccessor",
    "CurrentSessionAccessor",
    "AllSessionsAccessor",
)
```

**Файл:** `microclaw/toolkits/accessors/user.py` (новый)

```python
import uuid
from typing import Any, AsyncGenerator, Callable

from microclaw.dto import CronTask, User
from microclaw.users_storages.interfaces import UsersStorageInterface


class CurrentUserAccessor:
    def __init__(
        self,
        user_id: uuid.UUID,
        storage: UsersStorageInterface,
        writable: bool = False,
        invalidate_cache: Callable[[], None] | None = None,
    ):
        self.user_id = user_id
        self._storage = storage
        self._writable = writable
        self._invalidate_cache = invalidate_cache

    async def get(self) -> User | None:
        return await self._storage.get_user(self.user_id)

    async def get_crons(self) -> list[CronTask]:
        return await self._storage.get_crons(self.user_id)

    async def update_agent_settings(self, agent_settings: Any) -> User | None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        result = await self._storage.update_user(
            user_id=self.user_id, agent_settings=agent_settings
        )
        if self._invalidate_cache:
            self._invalidate_cache()
        return result

    async def create_cron(self, cron_task: CronTask) -> None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        return await self._storage.create_cron(self.user_id, cron_task)

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        return await self._storage.remove_cron(cron_id)


class AllUsersAccessor:
    def __init__(self, storage: UsersStorageInterface):
        self._storage = storage

    async def get_by_session(self, session_id: uuid.UUID) -> User | None:
        return await self._storage.get_user_by_session(session_id)

    async def get_by_channel(self, channel_key: str, channel_internal_id: str) -> User | None:
        return await self._storage.get_user_by_channel(channel_key, channel_internal_id)

    async def get_users(self) -> AsyncGenerator[User, None]:
        return self._storage.get_users()


class UserSessionsAccessor:
    """Provides session lookup for the current user across channels."""

    def __init__(self, user_id: uuid.UUID, storage: UsersStorageInterface):
        self._user_id = user_id
        self._storage = storage

    async def get_user_sessions(
        self, channel_key: str, channel_internal_id: str
    ) -> list[uuid.UUID]:
        return await self._storage.get_user_sessions(
            user_id=self._user_id,
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )

    async def get_actual_session(
        self, channel_key: str, channel_internal_id: str
    ) -> uuid.UUID | None:
        return await self._storage.get_actual_session(
            user_id=self._user_id,
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
```

**Файл:** `microclaw/toolkits/accessors/session.py` (новый)

```python
import uuid
from typing import AsyncGenerator

from microclaw.dto import AgentMessage
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface


class CurrentSessionAccessor:
    def __init__(
        self,
        session_id: uuid.UUID,
        storage: SessionsStorageInterface,
        writable: bool = False,
    ):
        self.session_id = session_id
        self._storage = storage
        self._writable = writable

    async def get_messages(self, filter: MessageFilter | None = None):
        filter = filter or MessageFilter(session_id=self.session_id)
        filter.session_id = self.session_id
        return self._storage.get_messages(filter=filter)

    async def add_message(self, message: AgentMessage) -> None:
        if not self._writable:
            raise PermissionError("Current session write access not granted")
        return await self._storage.add_message(self.session_id, message)

    async def get_context_size(self) -> int:
        return await self._storage.get_context_size(self.session_id)


class AllSessionsAccessor:
    def __init__(self, storage: SessionsStorageInterface):
        self._storage = storage

    async def get_sessions(self) -> AsyncGenerator[uuid.UUID, None]:
        return self._storage.get_sessions()

    async def get_messages(self, session_id: uuid.UUID, filter: MessageFilter | None = None):
        filter = filter or MessageFilter(session_id=session_id)
        filter.session_id = session_id
        return self._storage.get_messages(filter=filter)
```

---

### Шаг 1.5: Создать `ToolkitExecutionContext`

**Файл:** `microclaw/toolkits/context.py` (новый)

```python
import contextvars
import uuid
from dataclasses import dataclass

from microclaw.toolkits.accessors import (
    AllUsersAccessor,
    AllSessionsAccessor,
    CurrentSessionAccessor,
    CurrentUserAccessor,
    UserSessionsAccessor,
)
from microclaw.toolkits.dto import DiscoveryInfo


@dataclass(frozen=True)
class ToolkitExecutionContext:
    session_id: uuid.UUID
    request_id: uuid.UUID
    channel_key: str
    channel_internal_id: str

    # User / session accessors (controlled by ToolKitCapability)
    current_user_accessor: CurrentUserAccessor | None = None
    all_users_accessor: AllUsersAccessor | None = None
    user_sessions_accessor: UserSessionsAccessor | None = None
    current_session_accessor: CurrentSessionAccessor | None = None
    sessions_accessor: AllSessionsAccessor | None = None

    # Discovery (controlled by DiscoveryCapability)
    all_models: dict[str, DiscoveryInfo] | None = None
    all_toolkits: dict[str, DiscoveryInfo] | None = None
    all_skills: dict[str, DiscoveryInfo] | None = None
    all_agents: dict[str, DiscoveryInfo] | None = None
    all_mcp: dict[str, DiscoveryInfo] | None = None


TOOLKIT_CONTEXT = contextvars.ContextVar("toolkit_context", default=None)


def get_toolkit_context() -> ToolkitExecutionContext | None:
    return TOOLKIT_CONTEXT.get(None)
```

---

### Шаг 1.6: Удалить `BaseChannel` из contextvar

**Файл:** `microclaw/channels/base.py`

**Удалить:**
- `CHANNEL_CONTEXT = contextvars.ContextVar(...)`
- `get_current_channel()` classmethod
- `set_current_channel()` method

**Добавить:**
- `from microclaw.toolkits.capabilities import ToolKitCapability, DiscoveryCapability`
- `from microclaw.toolkits.context import ToolkitExecutionContext, TOOLKIT_CONTEXT`
- `from microclaw.toolkits.accessors import ...`
- `from microclaw.toolkits.dto import DiscoveryInfo`
- Метод `set_toolkit_context()`:

```python
@contextlib.contextmanager
def set_toolkit_context(
    self,
    session_id: uuid.UUID,
    request_id: uuid.UUID,
    channel_internal_id: str,
    user: User,
    agent: Agent,
):
    needed_caps = set()
    discovery_caps = set()
    write_caps = set()
    for toolkit in agent._toolkits.values():
        needed_caps.update(toolkit.required_capabilities)
        discovery_caps.update(toolkit.discovery_capabilities)
        write_caps.update(toolkit.write_capabilities)

    context = ToolkitExecutionContext(
        session_id=session_id,
        request_id=request_id,
        channel_key=self._channel_key,
        channel_internal_id=channel_internal_id,
    )

    # Accessors (ToolKitCapability)
    if ToolKitCapability.CURRENT_USER in needed_caps:
        context = dataclasses.replace(
            context,
            current_user_accessor=CurrentUserAccessor(
                user_id=user.id,
                storage=self._users_storage,
                writable=(ToolKitCapability.CURRENT_USER in write_caps),
                invalidate_cache=(
                    lambda: self._user_agents_cache.pop(user.id, None)
                    if ToolKitCapability.CURRENT_USER in write_caps
                    else None
                ),
            ),
        )

    if ToolKitCapability.ALL_USERS in needed_caps:
        context = dataclasses.replace(
            context,
            all_users_accessor=AllUsersAccessor(storage=self._users_storage),
        )

    if ToolKitCapability.CURRENT_USER in needed_caps:
        context = dataclasses.replace(
            context,
            user_sessions_accessor=UserSessionsAccessor(
                user_id=user.id,
                storage=self._users_storage,
            ),
        )

    if ToolKitCapability.CURRENT_SESSION in needed_caps:
        context = dataclasses.replace(
            context,
            current_session_accessor=CurrentSessionAccessor(
                session_id=session_id,
                storage=self._sessions_storage,
                writable=(ToolKitCapability.CURRENT_SESSION in write_caps),
            ),
        )

    if ToolKitCapability.ALL_SESSIONS in needed_caps:
        context = dataclasses.replace(
            context,
            sessions_accessor=AllSessionsAccessor(storage=self._sessions_storage),
        )

    # Discovery (DiscoveryCapability)
    if DiscoveryCapability.MODELS in discovery_caps:
        context = dataclasses.replace(
            context,
            all_models={k: DiscoveryInfo(name=k) for k in self._resolver._settings.models},
        )

    if DiscoveryCapability.TOOLKITS in discovery_caps:
        context = dataclasses.replace(
            context,
            all_toolkits={
                k: DiscoveryInfo(name=k, description=v.prompt)
                for k, v in self._resolver._settings.toolkits.items()
            },
        )

    if DiscoveryCapability.SKILLS in discovery_caps:
        context = dataclasses.replace(
            context,
            all_skills={
                k: DiscoveryInfo(name=(v if isinstance(v, str) else v.name))
                for k, v in self._resolver._settings.skills.items()
            },
        )

    if DiscoveryCapability.AGENTS in discovery_caps:
        current_agent_name = agent.name
        context = dataclasses.replace(
            context,
            all_agents={
                k: DiscoveryInfo(
                    name=v.identity.name if v.identity else k,
                    description=v.identity.description if v.identity else None,
                )
                for k, v in self._resolver._settings.agents.items()
                if k != current_agent_name
            },
        )

    if DiscoveryCapability.MCP in discovery_caps:
        context = dataclasses.replace(
            context,
            all_mcp={
                k: DiscoveryInfo(
                    name=(v.name or k),
                    description=v.description,
                )
                for k, v in self._resolver._settings.mcp.items()
            },
        )

    token = TOOLKIT_CONTEXT.set(context)
    try:
        yield
    finally:
        TOOLKIT_CONTEXT.reset(token)
```

---

### Шаг 1.7: Обновить каналы

**Файлы:**
- `microclaw/channels/telegram/base.py`
- `microclaw/channels/cli/channel.py`
- `microclaw/channels/vk/base.py`

В `_generate_and_send_answer` заменить:
```python
with (
    self.set_current_channel(),
    self.set_current_session_id(session_id),
    self.set_current_request_id(request_id),
):
```
на:
```python
with (
    self.set_toolkit_context(
        session_id=session_id,
        request_id=request_id,
        channel_internal_id=str(channel_internal_id),
        user=user,
        agent=agent,
    ),
    self.set_current_session_id(session_id),
    self.set_current_request_id(request_id),
):
```

> `channel_internal_id` уже доступен в `_generate_and_send_answer` каждого канала как локальная переменная / аргумент метода.

---

## Фаза 2: Миграция тулкитов

### Шаг 2.1: Мигрировать `CronToolKit`

**Файл:** `microclaw/toolkits/cron/toolkit.py`

```python
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context
from .settings import CronSettings


class CronToolKit(BaseToolKit[CronSettings]):
    required_capabilities = [ToolKitCapability.CURRENT_USER]
    write_capabilities = [ToolKitCapability.CURRENT_USER]
    discovery_capabilities = []

    @tool
    async def get_crons(self) -> list[CronTask]:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("No active channel context")
        return await ctx.current_user_accessor.get_crons()

    @tool
    async def create_cron(self, path: str, cron: str, ...) -> CronTask:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("No active channel context")
        cron_task = CronTask(id=uuid.uuid4(), path=path, cron=cron, ...)
        await ctx.current_user_accessor.create_cron(cron_task)
        return cron_task

    @tool
    async def remove_cron(self, cron_id: str) -> None:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("No active channel context")
        await ctx.current_user_accessor.remove_cron(uuid.UUID(cron_id))
```

---

### Шаг 2.2: Мигрировать `SessionsToolKit`

**Файл:** `microclaw/toolkits/sessions/toolkit.py`

```python
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context
from .settings import SessionsToolKitSettings


class SessionsToolKit(BaseToolKit[SessionsToolKitSettings]):
    required_capabilities = [
        ToolKitCapability.CURRENT_USER,
        ToolKitCapability.ALL_USERS,
        ToolKitCapability.ALL_SESSIONS,
    ]
    write_capabilities = []
    discovery_capabilities = []

    @tool
    async def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            return []
        user = await ctx.current_user_accessor.get()

        sessions = []
        async for session_id in ctx.sessions_accessor.get_sessions():
            owner = await ctx.all_users_accessor.get_by_session(session_id)
            if owner is None or owner.id != user.id:
                continue
            messages = []
            async for msg in ctx.sessions_accessor.get_messages(session_id):
                messages.append(MessageInfo(...))
            if messages:
                sessions.append(SessionInfo(...))
            if len(sessions) >= limit:
                break
        return sessions
```

---

### Шаг 2.3: Добавить capabilities во все остальные тулкиты

В каждый класс тулкита добавить:

```python
required_capabilities: list[ToolKitCapability] = []
write_capabilities: list[ToolKitCapability] = []
discovery_capabilities: list[DiscoveryCapability] = []
```

**Тулкиты:**
- `microclaw/toolkits/memory/toolkit.py`
- `microclaw/toolkits/filesystem/toolkit.py`
- `microclaw/toolkits/command/toolkit.py`
- `microclaw/toolkits/caldav/toolkit.py`
- `microclaw/toolkits/carddav/toolkit.py`
- `microclaw/toolkits/webdav/toolkit.py`
- `microclaw/toolkits/email/toolkit.py`
- `microclaw/toolkits/homeassistant/toolkit.py`
- `microclaw/toolkits/audio_tags/toolkit.py`
- `microclaw/toolkits/langchain_adapter/toolkit.py`
- `microclaw/toolkits/dynamic_loader/toolkit.py`

---

## Фаза 3: Реализация `AgentConfigToolKit`

### Шаг 3.1: Настройки тулкита

**Файл:** `microclaw/toolkits/agent_config/settings.py` (новый)

```python
from pydantic import BaseModel

from microclaw.toolkits.enums import PermissionModeEnum


class AgentConfigToolKitSettings(BaseModel):
    reset_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
```

---

### Шаг 3.2: Реализация тулкита

**Файл:** `microclaw/toolkits/agent_config/toolkit.py` (новый)

```python
from typing import Any

from langgraph.types import interrupt

from microclaw.agents.settings import AgentSettings
from microclaw.dto import DecisionEnum
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import ToolKitCapability, DiscoveryCapability
from microclaw.toolkits.context import get_toolkit_context
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
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        if ctx.all_models is None or model_name not in ctx.all_models:
            raise ValueError(f"Model '{model_name}' is not available.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model = model_name
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
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
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Identity updated: {agent_settings.identity.name} {agent_settings.identity.emoji}"

    @tool
    async def set_toolkits(self, toolkit_names: list[str]) -> str:
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
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Active toolkits: {toolkit_names}"

    @tool
    async def set_skills(self, skill_names: list[str]) -> str:
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
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Active skills: {skill_names}"

    @tool
    async def set_subagents(self, subagent_names: list[str]) -> str:
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
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Active subagents: {subagent_names}"

    @tool
    async def set_mcp(self, mcp_names: list[str]) -> str:
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
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Active MCP servers: {mcp_names}"

    # --- Individual advanced setting tools ---

    @tool
    async def set_temperature(self, temperature: float) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.temperature = temperature
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Temperature set to {temperature}."

    @tool
    async def set_max_tool_calls(self, max_tool_calls: int) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_tool_calls = max_tool_calls
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"max_tool_calls set to {max_tool_calls}."

    @tool
    async def set_max_model_calls(self, max_model_calls: int) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_model_calls = max_model_calls
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"max_model_calls set to {max_model_calls}."

    @tool
    async def set_enable_summarization(self, enable_summarization: bool) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.enable_summarization = enable_summarization
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Summarization {'enabled' if enable_summarization else 'disabled'}."

    @tool
    async def set_enable_memory_flush(self, enable_memory_flush: bool) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.enable_memory_flush = enable_memory_flush
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"Memory flush {'enabled' if enable_memory_flush else 'disabled'}."

    @tool
    async def set_max_memory_flush_tokens(self, max_memory_flush_tokens: int) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_memory_flush_tokens = max_memory_flush_tokens
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"max_memory_flush_tokens set to {max_memory_flush_tokens}."

    @tool
    async def set_max_tool_output_chars(self, max_tool_output_chars: int) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.max_tool_output_chars = max_tool_output_chars
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"max_tool_output_chars set to {max_tool_output_chars}."

    @tool
    async def set_model_max_retries(self, model_max_retries: int) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model_max_retries = model_max_retries
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"model_max_retries set to {model_max_retries}."

    @tool
    async def set_model_retry_backoff_factor(self, model_retry_backoff_factor: float) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model_retry_backoff_factor = model_retry_backoff_factor
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"model_retry_backoff_factor set to {model_retry_backoff_factor}."

    @tool
    async def set_model_retry_initial_delay(self, model_retry_initial_delay: float) -> str:
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("Not available outside channel context.")
        user = await ctx.current_user_accessor.get()
        agent_settings = AgentSettings.model_validate(user.agent) if user.agent else AgentSettings()
        agent_settings.model_retry_initial_delay = model_retry_initial_delay
        await ctx.current_user_accessor.update_agent_settings(agent_settings.model_dump(mode="json"))
        return f"model_retry_initial_delay set to {model_retry_initial_delay}."

    @tool
    async def reset_agent_config(self) -> str:
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
```

---

### Шаг 3.3: `__init__.py`

**Файл:** `microclaw/toolkits/agent_config/__init__.py` (новый)

```python
from .settings import AgentConfigToolKitSettings
from .toolkit import AgentConfigToolKit

__all__ = ("AgentConfigToolKit", "AgentConfigToolKitSettings")
```

---

## Фаза 4: Тесты

### Шаг 4.1: Тесты контекста и accessors

**Файл:** `tests/toolkits/test_accessors.py` (новый)

```python
import pytest
import uuid
from unittest.mock import MagicMock, AsyncMock

from microclaw.toolkits.accessors.user import CurrentUserAccessor, AllUsersAccessor, UserSessionsAccessor
from microclaw.toolkits.accessors.session import CurrentSessionAccessor, AllSessionsAccessor


@pytest.mark.asyncio
async def test_current_user_accessor_read_only():
    storage = MagicMock()
    acc = CurrentUserAccessor(user_id=uuid.uuid4(), storage=storage, writable=False)
    await acc.get()
    with pytest.raises(PermissionError):
        await acc.update_agent_settings(None)


@pytest.mark.asyncio
async def test_current_user_accessor_writable():
    storage = MagicMock()
    storage.update_user = AsyncMock(return_value=MagicMock())
    invalidate = MagicMock()
    acc = CurrentUserAccessor(
        user_id=uuid.uuid4(), storage=storage, writable=True, invalidate_cache=invalidate
    )
    await acc.update_agent_settings(None)
    storage.update_user.assert_awaited_once()
    invalidate.assert_called_once()


@pytest.mark.asyncio
async def test_user_sessions_accessor():
    storage = MagicMock()
    storage.get_user_sessions = AsyncMock(return_value=[uuid.uuid4()])
    acc = UserSessionsAccessor(user_id=uuid.uuid4(), storage=storage)
    sessions = await acc.get_user_sessions("telegram", "12345")
    storage.get_user_sessions.assert_awaited_once()
    assert len(sessions) == 1
```

---

### Шаг 4.2: Тесты `AgentConfigToolKit`

**Файл:** `tests/toolkits/test_agent_config.py` (новый)

Сценарии:
- `test_get_my_agent_config__default`
- `test_get_my_agent_config__with_override`
- `test_get_available_options`
- `test_set_model__invalid`
- `test_set_identity`
- `test_set_toolkits`
- `test_set_skills`
- `test_set_subagents`
- `test_set_mcp`
- `test_set_temperature`
- `test_set_max_tool_calls`
- `test_set_enable_summarization`
- `test_reset_agent_config`
- `test_cache_invalidation_on_update`

---

## Фаза 5: Интеграция

### Шаг 5.1: Добавить тулкит в конфигурацию

**Файл:** `config.yaml`

```yaml
toolkits:
  agent_config:
    path: microclaw.toolkits.agent_config.AgentConfigToolKit
    args:
      reset_mode: request
```

---

### Шаг 5.2: Ручная проверка

```bash
python -m microclaw channels cli
```

**Сценарии:**
1. "Покажи мой конфиг" → `get_my_agent_config()`
2. "Какие модели доступны?" → `get_available_options("models")`
3. "Поменяй модель на gpt-4o" → `set_model("gpt-4o")`
4. "Поменяй моё имя на Клаус" → `set_identity(name="Клаус")`
5. "Включи тулкит cron" → `set_toolkits(["memory", "cron"])`
6. "Добавь MCP сервер web_search" → `set_mcp(["web_search"])`
7. "Установи temperature 0.5" → `set_temperature(0.5)`
8. "Сбрось мои настройки" → `reset_agent_config()`

---

## Справка

### Разделение capability types

- `ToolKitCapability` — runtime доступ к users/sessions. Нужен для тулкитов, которые читают/пишут сессии, crons, user.agent.
- `DiscoveryCapability` — read-only discovery списков моделей, тулкитов, скиллов, агентов, MCP. Нужен для тулкитов, которые показывают пользователю доступные опции.

Разделение ортогонально: тулкит может иметь `ToolKitCapability.CURRENT_USER` без `DiscoveryCapability.MODELS`, и наоборот.

### `DiscoveryInfo` DTO

```python
class DiscoveryInfo(BaseModel):
    name: str
    description: str | None = None
```

Единая модель для всех discoverable сущностей. Никаких настроек, паролей, URL.

### `UserSessionsAccessor`

Отдельный accessor для получения сессий текущего пользователя:
- `get_user_sessions(channel_key, channel_internal_id) -> list[UUID]`
- `get_actual_session(channel_key, channel_internal_id) -> UUID | None`

Привязан к `user_id` в конструкторе, не требует его передачи в каждый вызов.

### Без `getattr` — явный `channel_internal_id`

Вместо `getattr(self, "_current_channel_internal_id", "default")` метод `set_toolkit_context()` принимает `channel_internal_id: str` как явный аргумент. Каждый канал передаёт свой `channel_internal_id` (Telegram — chat_id, CLI — "cli", VK — peer_id).

### Почему без `AGENT_CACHE_INVALIDATION`

Кэш агента — внутренняя оптимизация канала. `CurrentUserAccessor.update_agent_settings()` вызывает `invalidate_cache_callback()` после записи. Тулкит просто делает `ctx.current_user_accessor.update_agent_settings(...)`.

### Работа в cron-задачах

- **С каналом**: `start_conversation()` → канал создаёт `ToolkitExecutionContext` → тулкит работает.
- **Без канала**: `agent.ask()` без контекста → `get_toolkit_context()` вернёт `None`.

### Безопасность

- **Capability-based:** канал передаёт в `ToolkitExecutionContext` только то, что запрошено.
- **Scoped accessors:** `CurrentUserAccessor` привязан к `user_id`, `CurrentSessionAccessor` к `session_id`.
- **Writable-флаг:** `PermissionError` на write без `write_capabilities`.
- **Авто-инвалидация кэша:** handle сам сбрасывает кэш.
- **Нет resolver в контексте:** discovery — только `DiscoveryInfo` DTOs.
- **Валидация:** `AgentSettings.model_validate()` перед сохранением.
- **PermissionMode:** `reset_agent_config` требует подтверждения (`interrupt`).

### Возможные расширения (не в MVP)

- `edit_mode: PermissionModeEnum` для setter-ов.
- `get_agent_config_diff()`.
- `import_agent_config(yaml_string)`.
- Дополнительные capabilities: `FILESYSTEM`, `COMMAND`, `NETWORK`.
- Sandbox-изоляция внешних тулкитов через subprocess / MCP.
