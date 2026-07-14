# План реализации: AgentConfig ToolKit

## Цель

Позволить пользователю самостоятельно настраивать персональные параметры своего агента (`AgentSettings`) через естественный язык, без редактирования YAML. Настройки хранятся в `User.agent` (per-user override) и применяются через механизм `BaseChannel.get_agent_for_user()`.

## Архитектурный рефакторинг

### Проблема

`BaseChannel` лежит в `ContextVar` (`CHANNEL_CONTEXT`). Тулкит через `BaseChannel.get_current_channel()` получает доступ ко всему: `users_storage`, `sessions_storage`, `resolver`, `syncer`.

### Решение: Capability-based `ToolkitExecutionContext`

Каждый тулкит декларирует:
- `required_capabilities: list[ToolKitCapability]` — какие сущности нужны
- `write_capabilities: list[ToolKitCapability]` — какие из них доступны на запись

Канал собирает union и создаёт `ToolkitExecutionContext`, содержащий **scoped accessor-объекты** с `writable` флагом. Никакого `BaseChannel`, `resolver` или `MicroclawSettings`.

### `ToolKitCapability` — только сущности

```python
class ToolKitCapability(str, enum.Enum):
    CURRENT_USER = "current_user"        # доступ к данным текущего пользователя (crons, get_user)
    ALL_USERS = "all_users"              # доступ ко всем пользователям (get_by_session, get_by_channel)
    CURRENT_SESSION = "current_session"  # доступ к текущей сессии
    ALL_SESSIONS = "all_sessions"        # доступ ко всем сессиям
    MODELS = "models"                    # discovery: список имён моделей
    TOOLKITS = "toolkits"                # discovery: список имён тулкитов
    SKILLS = "skills"                    # discovery: список имён скиллов
    AGENTS = "agents"                    # discovery: список имён агентов (subagents)
```

> Нет `CURRENT_USER` как отдельной capability. Если тулкит запросил `USERS`, он получает и данные текущего пользователя, и storage-доступ. Если нужен read-only доступ к данным пользователя без доступа к storage — это `USERS` без `USERS` в `write_capabilities` (accessor блокирует write-методы).

### Декларация в тулкитах

```python
class AgentConfigToolKit(BaseToolKit[AgentConfigToolKitSettings]):
    required_capabilities = [
        ToolKitCapability.CURRENT_USER,
        ToolKitCapability.MODELS,
        ToolKitCapability.TOOLKITS,
        ToolKitCapability.SKILLS,
        ToolKitCapability.AGENTS,
    ]
    write_capabilities = [
        ToolKitCapability.CURRENT_USER,  # позволяет менять user.agent (и автоматически инвалидирует кэш агента)
    ]

class SessionsToolKit(BaseToolKit[SessionsToolKitSettings]):
    required_capabilities = [
        ToolKitCapability.USERS,
        ToolKitCapability.SESSIONS,
    ]
    write_capabilities = []  # только читает сессии и фильтрует по пользователю

class CronToolKit(BaseToolKit[CronSettings]):
    required_capabilities = [ToolKitCapability.USERS]
    write_capabilities = [ToolKitCapability.USERS]  # может создавать/удалять crons
```

### `ToolkitExecutionContext`

```python
@dataclass(frozen=True)
class ToolkitExecutionContext:
    session_id: UUID
    request_id: UUID
    channel_key: str
    channel_internal_id: str

    # Accessors — scoped и с writable-флагом
    users: UsersAccessor | None = None
    sessions: SessionsAccessor | None = None

    # Discovery — plain list[str]
    models: list[str] | None = None
    toolkits: list[str] | None = None
    skills: list[str] | None = None
    agents: list[str] | None = None

    # Side effects
    invalidate_user_agent_cache: Callable[[], None] | None = None
```

### Accessors

Accessor — обёртка над storage, которая:
- хранит `user_id`/`session_id` (scoped)
- знает `writable` флаг
- бросает `PermissionError` на write-операции, если `writable=False`

```python
class UsersAccessor:
    def __init__(self, user_id: UUID, storage: UsersStorageInterface, writable: bool = False):
        self.user_id = user_id
        self._storage = storage
        self._writable = writable

    async def get(self) -> User | None:
        return await self._storage.get_user(self.user_id)

    async def get_crons(self) -> list[CronTask]:
        return await self._storage.get_crons(self.user_id)

    async def update_agent_settings(self, agent_settings: AgentSettings | None) -> User | None:
        self._ensure_writable()
        return await self._storage.update_user(
            user_id=self.user_id, agent_settings=agent_settings
        )

    async def create_cron(self, cron_task: CronTask) -> None:
        self._ensure_writable()
        return await self._storage.create_cron(self.user_id, cron_task)

    async def remove_cron(self, cron_id: UUID) -> None:
        self._ensure_writable()
        return await self._storage.remove_cron(cron_id)

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise PermissionError("Users write access not granted")
```

```python
class SessionsAccessor:
    def __init__(self, session_id: UUID, storage: SessionsStorageInterface, writable: bool = False):
        self.session_id = session_id
        self._storage = storage
        self._writable = writable

    async def get_messages(self, filter: MessageFilter):
        filter.session_id = self.session_id
        return self._storage.get_messages(filter=filter)

    async def add_message(self, message: AgentMessage) -> None:
        self._ensure_writable()
        return await self._storage.add_message(self.session_id, message)

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise PermissionError("Sessions write access not granted")
```

> Тулкит **может** достать `accessor._storage`, но это intentional. Мы защищаем от accidental доступа к чужим пользователям — `user_id` уже привязан.

### Использование в тулкитах

```python
# AgentConfigToolKit
async def set_model(self, model_name: str) -> str:
    ctx = get_toolkit_context()
    if ctx is None:
        return "Not available outside channel context."
    if ctx.models is None or model_name not in ctx.models:
        return f"Model '{model_name}' is not available."

    user = await ctx.users.get()
    agent_dict = user.agent or {}
    agent_dict["model"] = model_name

    await ctx.users.update_agent_settings(AgentSettings(**agent_dict))
    if ctx.invalidate_user_agent_cache:
        ctx.invalidate_user_agent_cache()
    return f"Model set to {model_name}."
```

```python
# SessionsToolKit
async def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
    ctx = get_toolkit_context()
    user = await ctx.users.get()

    sessions = []
    async for session_id in ctx.sessions.get_messages(filter=MessageFilter(session_id=None)):
        owner = await ctx.users._storage.get_user_by_session(session_id)
        if owner is None or owner.id != user.id:
            continue
        # ...
```

```python
# CronToolKit
async def get_crons(self) -> list[CronTask]:
    ctx = get_toolkit_context()
    return await ctx.users.get_crons()

async def create_cron(self, path: str, cron: str) -> CronTask:
    ctx = get_toolkit_context()
    cron_task = CronTask(id=uuid.uuid4(), path=path, cron=cron)
    await ctx.users.create_cron(cron_task)
    return cron_task
```

### Сборка context при вызове `agent.ask()`

```python
required_caps = set()
write_caps = set()
for toolkit in agent_toolkits.values():
    required_caps.update(getattr(toolkit, "required_capabilities", []))
    write_caps.update(getattr(toolkit, "write_capabilities", []))

context = ToolkitExecutionContext(
    session_id=session_id,
    request_id=request_id,
    channel_key=self._channel_key,
    channel_internal_id=str(channel_internal_id),
)

if ToolKitCapability.USERS in required_caps:
    context.users = UsersAccessor(
        user_id=user.id,
        storage=users_storage,
        writable=(ToolKitCapability.USERS in write_caps),
    )

if ToolKitCapability.SESSIONS in required_caps:
    context.sessions = SessionsAccessor(
        session_id=session_id,
        storage=sessions_storage,
        writable=(ToolKitCapability.SESSIONS in write_caps),
    )

if ToolKitCapability.MODELS in required_caps:
    context.models = list(self._resolver._settings.models.keys())
if ToolKitCapability.TOOLKITS in required_caps:
    context.toolkits = list(self._resolver._settings.toolkits.keys())
if ToolKitCapability.SKILLS in required_caps:
    context.skills = list(self._resolver._settings.skills.keys())
if ToolKitCapability.AGENTS in required_caps:
    context.agents = [k for k in self._resolver._settings.agents.keys() if k != current_agent_key]

if ToolKitCapability.AGENT_CACHE_INVALIDATION in required_caps:
    context.invalidate_user_agent_cache = lambda: self._user_agents_cache.pop(user.id, None)

with set_toolkit_context(context):
    async for msg in agent.ask(...):
        ...
```

### Миграция существующих тулкитов

| Тулкит | `required_capabilities` | `write_capabilities` | Миграция |
|--------|------------------------|---------------------|----------|
| `SessionsToolKit` | `USERS`, `SESSIONS` | `[]` | `BaseChannel` → `get_toolkit_context()`; `get_user_id()` → `ctx.users.user_id`; `get_users_storage()` → `ctx.users` (чтение); `get_sessions_storage()` → `ctx.sessions` (чтение) |
| `CronToolKit` | `USERS` | `USERS` | `BaseChannel` → `get_toolkit_context()`; `get_user_id()` → `ctx.users.user_id`; `_get_users_storage()` → `ctx.users` (запись) |
| `TelegramToolKit` | — | — | **Без изменений** — канальный тулкит |

## Контекст (неизменяемый от MVP)

- `User.agent: dict[str, Any] | None` — хранит override `AgentSettings`.
- `BaseChannel.get_agent_for_user(user)` создаёт `Agent` из `AgentSettings(**user.agent)`.
- Изменения `user.agent` требуют инвалидации кэша `_user_agents_cache`.
- Merge, а не replace, при обновлении частичных полей.

## Набор инструментов (`AgentConfigToolKit`)

| Инструмент | Назначение |
|------------|------------|
| `get_my_agent_config()` | Текущий персональный конфиг или «дефолтные настройки канала». |
| `list_available_options(option_type)` | Discovery: `"models"`, `"toolkits"`, `"skills"`, `"subagents"`. |
| `set_model(model_name)` | Установить модель (валидируется против `ctx.models`). |
| `set_identity(...)` | Обновить личность. Все параметры optional, merge. |
| `set_toolkits(toolkit_names)` | Заменить активные тулкиты (валидируется против `ctx.toolkits`). |
| `set_skills(skill_names)` | Заменить скиллы (валидируется против `ctx.skills`). |
| `set_subagents(subagent_names)` | Заменить субагентов (валидируется против `ctx.agents`). |
| `set_advanced_settings(...)` | Числовые/булевые параметры. Все optional. |
| `reset_agent_config()` | Удалить `user.agent`. Требует подтверждения через `interrupt`. |

## Структура файлов

```
microclaw/toolkits/
├── capabilities.py              # ToolKitCapability enum
├── context.py                   # ToolkitExecutionContext, TOOLKIT_CONTEXT, accessors
└── base.py                      # [mod] required_capabilities, write_capabilities

microclaw/toolkits/agent_config/
├── __init__.py
├── settings.py                  # AgentConfigToolKitSettings
└── toolkit.py                   # AgentConfigToolKit

microclaw/channels/base.py
└── [mod] удалить CHANNEL_CONTEXT, добавить set_toolkit_context()

microclaw/toolkits/sessions/toolkit.py
└── [mod] required_capabilities + ToolkitExecutionContext

microclaw/toolkits/cron/toolkit.py
└── [mod] required_capabilities + ToolkitExecutionContext

tests/toolkits/
├── test_agent_config.py
└── test_context.py
```

## План реализации

### Шаг 0: Инфраструктура

1. **`microclaw/toolkits/capabilities.py`** — `ToolKitCapability` enum.
2. **`microclaw/toolkits/base.py`** — добавить `required_capabilities: list[ToolKitCapability] = []` и `write_capabilities: list[ToolKitCapability] = []`.
3. **`microclaw/toolkits/context.py`**:
   - `ToolkitExecutionContext` (frozen dataclass)
   - `UsersAccessor`, `SessionsAccessor` (scoped, `writable` флаг)
   - `TOOLKIT_CONTEXT: ContextVar`
   - `get_toolkit_context()`, `set_toolkit_context()`

4. **`microclaw/channels/base.py`**:
   - Удалить `CHANNEL_CONTEXT`, `get_current_channel()`, `set_current_channel()`.
   - Добавить `set_toolkit_context()` — capability-based сборка.

5. Обновить `_generate_and_send_answer` во всех каналах (Telegram, CLI, VK).

### Шаг 1: Миграция `SessionsToolKit` и `CronToolKit`

- `SessionsToolKit`:
  - `required_capabilities = [ToolKitCapability.USERS, ToolKitCapability.SESSIONS]`
  - `write_capabilities = []`
  - `get_current_channel()` → `get_toolkit_context()`
  - `get_user_id()` → `ctx.users.user_id`
  - `get_users_storage()` → `ctx.users`
  - `get_sessions_storage()` → `ctx.sessions`

- `CronToolKit`:
  - `required_capabilities = [ToolKitCapability.USERS]`
  - `write_capabilities = [ToolKitCapability.USERS]`
  - `get_current_channel()` → `get_toolkit_context()`
  - `get_user_id()` → `ctx.users.user_id`
  - `_get_users_storage()` → `ctx.users`

### Шаг 2: Настройки тулкита

`microclaw/toolkits/agent_config/settings.py`:
- `AgentConfigToolKitSettings(BaseModel)`
- Поле: `reset_mode: PermissionModeEnum = PermissionModeEnum.REQUEST`

### Шаг 3: Реализация `AgentConfigToolKit`

```python
class AgentConfigToolKit(BaseToolKit[AgentConfigToolKitSettings]):
    required_capabilities = [
        ToolKitCapability.USERS,
        ToolKitCapability.MODELS,
        ToolKitCapability.TOOLKITS,
        ToolKitCapability.SKILLS,
        ToolKitCapability.AGENTS,
        ToolKitCapability.AGENT_CACHE_INVALIDATION,
    ]
    write_capabilities = [ToolKitCapability.USERS]
```

**Приватные:** `_get_context()`, `_get_user()`, `_get_user_agent_dict()`, `_save_agent_updates()`, `_validate_agent_settings()`.

**Публичные:** 9 тулзов. `reset_agent_config()` через `interrupt()`.

### Шаг 4: Регистрация

`microclaw/toolkits/agent_config/__init__.py`.

### Шаг 5: Тесты

- `test_context.py`:
  - Accessor `writable=False` → `PermissionError` на write.
  - Capability-based сборка → тулкит без `SESSIONS` не получает `ctx.sessions`.
- `test_agent_config.py`:
  - Полный сценарий: get, list, set, merge, reset, invalid model, cache invalidation.

### Шаг 6: Интеграция

1. Добавить `agent_config` в тулкиты агента.
2. Запустить CLI-канал.
3. Проверить: "Покажи мой конфиг", "Поменяй моё имя", "Сбрось мои настройки".

## Работа в cron-задачах

- **С каналом**: `start_conversation()` → канал создаёт `ToolkitExecutionContext` → тулкит работает.
- **Без канала**: `agent.ask()` без контекста → `get_toolkit_context()` вернёт `None`.

```python
ctx = get_toolkit_context()
if ctx is None:
    return "Agent configuration is only available inside an active channel context."
```

## Безопасность и ограничения

- **Capability-based доступ:** канал передаёт в `ToolkitExecutionContext` только то, что тулкиты запросили. Тулкит без `MODELS` не получит список моделей.
- **Scoped:** `UsersAccessor` и `SessionsAccessor` привязаны к `user_id`/`session_id` и не позволяют обратиться к другому.
- **Writable-флаг:** accessor бросает `PermissionError` на write-операции, если capability не была декларирована в `write_capabilities`.
- **Нет resolver / MicroclawSettings в контексте:** discovery — только plain `list[str]`.
- **Валидация:** `set_model` проверяет имя через `ctx.models` + `AgentSettings.model_validate()`.
- **PermissionMode:** `reset_agent_config` требует подтверждения (`interrupt`).

## Возможные расширения (не в MVP)

- `edit_mode: PermissionModeEnum` для setter-ов.
- `get_agent_config_diff()`.
- `import_agent_config(yaml_string)`.
- Дополнительные capabilities: `FILESYSTEM`, `COMMAND`, `NETWORK`.
- Sandbox-изоляция внешних тулкитов через subprocess / MCP.
