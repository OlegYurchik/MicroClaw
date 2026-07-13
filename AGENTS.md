# MicroClaw — Agent Context

> AI agent micro-framework. Multi-user, distributed, toolkit-driven.
> Python 3.13+, async-first, configuration-driven.

## Project Overview

MicroClaw is a scalable framework for building personal AI assistants.
Core concepts:

- **Agents** — LLM entities with identity, tools, and optional subagents.
- **Channels** — User-facing interfaces (Telegram, CLI, REST API, etc.).
- **Toolkits** — Modular integrations (calendar, email, files, smart home, etc.).
- **Storages** — Pluggable persistence for sessions and users (filesystem, database, memory).
- **Syncer** — Cross-instance state synchronization (Redis-backed memory syncer).
- **Cron** — Scheduled tasks via APScheduler.

## Directory Structure

```
microclaw/
├── agents/              # Agent orchestration, prompts, subagents
├── channels/            # Communication channels (telegram, cli, base)
├── toolkits/            # Agent toolkits (caldav, email, webdav, memory, etc.)
├── sessions_storages/   # Session persistence (filesystem, database, memory)
├── users_storages/      # User persistence (filesystem, database, memory)
├── syncers/             # Multi-instance sync (memory/Redis)
├── cron/                # Scheduled tasks
├── api/rest/            # FastAPI REST endpoints
├── stt/                 # Speech-to-text integration
├── utils/               # Helpers, database utilities
├── dto.py               # Shared data models (AgentMessage, Spending, User)
├── settings.py          # Root YAML configuration loader
├── resolver.py          # Dependency injection container
├── service.py           # Core service orchestrator (facet.AsyncioServiceMixin)
└── cli.py               # Typer CLI entry point

tests/                   # pytest + pytest-asyncio tests
├── conftest.py          # Shared fixtures (agent, channel, storages, syncer)
├── factories.py         # FakeChannel, FakeChatModel for testing
└── agents/              # Agent-related tests

.ai/                     # Internal project documentation
```

## Tech Stack

- **Language**: Python >=3.13
- **AI/LLM**: LangChain + langchain-mcp-adapters, deepagents, tiktoken
- **Providers**: OpenAI, Cloud.ru (Evolution), Ollama
- **Telegram**: aiogram 3.25+
- **Web**: FastAPI + Uvicorn
- **DB**: SQLModel / SQLAlchemy 2.0, Alembic
- **Scheduling**: APScheduler
- **Config**: Pydantic 2.12+, pydantic-settings, PyYAML (with `!env` and `!include`)
- **Logging**: loguru
- **CLI UI**: Textual (planned for TUI)
- **Package manager**: `uv` (uv.lock present)
- **Linter**: ruff

## Build & Run

Install dependencies (example with Telegram + OpenAI):

```bash
uv pip install -e ".[telegram,openai]"
```

Other extras: `database`, `caldav`, `carddav`, `webdav`, `email`, `homeassistant`, `discogs`, `vk`, `cloudru`, `ollama`, `audio_tags`, `tasks`.

Run Telegram bot:

```bash
python -m microclaw channels telegram
```

Run CLI channel:

```bash
python -m microclaw channels cli
```

Run full service:

```bash
python -m microclaw run
```

## Configuration

Configuration is loaded from `config.yaml` (and/or env vars with prefix `MICROCLAW__`).

Key sections:

```yaml
providers:
  cloud_ru:
    base_url: https://foundation-models.api.cloud.ru/v1
    api_type: openai
    api_key: !env CLOUDRU_API_KEY

models:
  qwen3_coder_next:
    id: qwen3-coder-next
    provider: cloud_ru
    costs:
      input: 0.15
      output: 0.6
      currency: "RUB"

agents:
  personal_assistant:
    model: qwen3_coder_next
    identity:
      name: "MicroClaw"
      emoji: "🤖"
      creature: "AI"
      vibe: "helpful"
    toolkits:
      - memory
      - personal_calendar
    subagents:
      - butler

toolkits:
  personal_calendar:
    path: microclaw.toolkits.caldav.CalDAVToolKit
    args:
      url: !env CALDAV_URL
      username: !env CALDAV_USER
      password: !env CALDAV_PASS

channels:
  telegram:
    agent: personal_assistant
    sessions_storage: default
    users_storage: default
    type: telegram
    method: polling
    token: !env TELEGRAM_BOT_TOKEN
```

**Security rule**: Never commit secrets. Always use `!env VAR_NAME` or `!include` for sensitive data.

## Code Conventions

### Naming
- `snake_case` for files, functions, variables, YAML keys.
- `PascalCase` for classes.
- Abstract classes prefixed with `Base` (`BaseChannel`, `BaseToolKit`).
- Interfaces suffixed with `Interface` (`SessionsStorageInterface`).
- Private attributes/methods prefixed with `_`.

### Types
- Always use type hints for parameters and return values.
- Use `X | None` instead of `Optional[X]`.
- Use `Self` for methods returning `self`.
- Import from `typing` when needed: `AsyncGenerator`, `Sequence`, etc.

### Async
- **All I/O must be async.** Use `aiofiles` for file I/O, async DB drivers, etc.
- Never mix sync blocking calls inside async code.

### Pydantic
- All data structures are Pydantic models.
- Configuration classes extend `BaseSettings`/`BaseModel`.
- Use `Field()` with descriptions and constraints (`ge=`, `le=`).
- Use `@model_validator` for cross-field validation.
- Serialize with `model_dump(mode="json")`.

### Error Handling
- Catch expected errors gracefully; log with context.
- Never expose stack traces to end users.
- Tool errors are caught by middleware (`_handle_tool_errors`) and returned as `ToolMessage`.
- Specific exceptions preferred over generic `Exception`.

### Logging
- Use `loguru`. Bind context when possible:
  ```python
  bound_logger = logger.bind(request_id=request_id, session_id=session_id)
  bound_logger.info("Agent ask started")
  ```
- Never log secrets.

### Import Order
1. Standard library
2. Third-party
3. Absolute local imports (`from microclaw...`)
4. Relative local imports (`from .settings import ...`)

## Architecture Patterns

### 1. Interface-First Design
Define abstract interfaces before implementations:

```python
class SessionsStorageInterface(abc.ABC):
    @abc.abstractmethod
    async def add_message(self, session_id: UUID, message: AgentMessage) -> None: ...
```

Then implement `FilesystemSessionsStorage`, `DatabaseSessionsStorage`, etc.

### 2. Dependency Injection
- Components receive dependencies via constructors.
- `DependencyResolver` wires everything together from configuration.
- Never instantiate LLM clients or storages directly inside business logic.

### 3. Service Mixin
Long-running services extend `facet.AsyncioServiceMixin`:

```python
class MyChannel(facet.AsyncioServiceMixin):
    async def start(self): ...
    async def stop(self): ...
    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]: ...
```

### 4. Factory Pattern
Factories resolve settings strings to implementations:
- `get_sessions_storage()`, `get_users_storage()`, `get_channel()`, `get_toolkit()`, `get_syncer()`, `get_cron_task()`.

### 5. Toolkit Plugin System
Toolkits extend `BaseToolKit[SettingsType]` and expose tools via `@tool` decorator:

```python
from microclaw.toolkits import BaseToolKit, tool

class MyToolKit(BaseToolKit[MySettings]):
    @tool
    async def do_something(self, query: str) -> str:
        """Short description used by LLM."""
        return result
```

Tools are prefixed with toolkit key: `my_toolkit_do_something`.

### 6. Permission System
Every toolkit operation can have mode: `ALLOW`, `REQUEST`, `DENY`.
When mode is `REQUEST`, the channel asks user for confirmation before execution.
Use `BaseToolKit.request_confirmation()` or check `PermissionModeEnum` in toolkit code.

### 7. Context Variables
Channels use `contextvars` to track current state:
- `BaseChannel.CHANNEL_CONTEXT`
- `BaseChannel.SESSION_ID_CONTEXT`
- `BaseChannel.REQUEST_ID_CONTEXT`

Used inside `Agent.ask()` to bind logger context without passing IDs through every call.

## Key Data Models

### `AgentMessage`
```python
role: str          # user | assistant | system | tool | request_confirmation
text: str | None
chunked_message_id: str | None   # groups streaming chunks
spending: Spending | None
is_summary: bool
audio: bytes | None
audio_format: str | None
```

### `Spending`
```python
input_tokens: int
output_tokens: int
cache_read_tokens: int
cache_write_tokens: int
audio_input_seconds: int
audio_output_seconds: int
cost: float
currency: str = "$"
```

### `User`
```python
id: UUID
role: UserRoleEnum   # USER | ADMIN
agent: dict[str, Any] | None   # per-user agent override
```

## Testing

Tests use **pytest** + **pytest-asyncio**.

Shared fixtures in `tests/conftest.py`:
- `agent_settings`, `model_settings`, `provider_settings`
- `toolkits`, `memory_toolkit`
- `client` (AsyncMock)
- `channel` (MagicMock)
- `agent`, `make_agent`
- `sessions_storage` (`MemorySessionsStorage`)
- `users_storage` (`MemoryUsersStorage`)
- `syncer` (`MemorySyncer`)
- `base_channel` (FakeChannel from `tests/factories`)

Custom test helpers in `tests/factories.py`:
- `FakeChatModel` — emulates LLM responses for unit tests.
- `FakeChannel` — minimal channel implementation for testing.

Run tests:

```bash
pytest
```

## Important Implementation Details

### Agent.ask() Flow
1. Convert `AgentMessage` list to LangChain messages.
2. Generate system prompt via Jinja2 template (`agents/templates/agent_prompt.j2`).
3. Combine tools: toolkit tools + MCP tools + channel tools + subagent tools.
4. Apply middleware: tool error handling, parallel tool call disabling, retry logic, call limits.
5. Stream events via `agent.astream_events()`.
6. Track tokens with tiktoken (fallback to `cl100k_base`).
7. Yield streaming chunks or accumulate full response.
8. Return spending summary.

Limits:
- `max_tool_calls`: 25 (configurable)
- `max_model_calls`: configurable
- Recursion limit: 1000

### Automatic Summarization
Triggered in `BaseChannel.summarize_dialog_if_needed()` when context exceeds threshold (default 80% of model context window).

Flow:
1. Extract important info for long-term memory.
2. Extract daily info.
3. Append to `MemoryToolKit` (general + date-specific).
4. Summarize dialogue.
5. Store summary as `AgentMessage(is_summary=True)`.
6. Reset tracked context size.

### Subagent Delegation
Agents can have `subagents` configured. Subagents are exposed as tools to the main agent via `SubAgentToolKit`.
Subagents run with isolated context and `max_turns` limit. Results are summarized if too long.
Subagent tool names are prefixed with agent name: `butler_homeassistant`.

### MCP Support
MCP servers configured in YAML. `Agent` creates `MultiServerMCPClient` at init.
Supports HTTP, WebSocket, and stdio transports.
MCP tools are prefixed with server name.

### Cron Tasks
System tasks (e.g., `FlushToMemoryCronTask`) run via APScheduler.
User tasks stored per-user in `UsersStorage`.

## Rules for New Features

### Adding a New Toolkit
1. Create directory under `microclaw/toolkits/<name>/`.
2. Implement class extending `BaseToolKit[<SettingsType>]`.
3. Define settings model in `settings.py`.
4. Register in `microclaw/toolkits/__init__.py` or reference via full path in config.
5. Add optional dependency group in `pyproject.toml`.
6. Add tests in `tests/toolkits/` if applicable.

### Adding a New Channel
1. Create directory under `microclaw/channels/<name>/`.
2. Extend `BaseChannel` and implement `start_conversation()`.
3. Implement channel-specific toolkit if needed (`get_toolkit()`).
4. Add settings in `microclaw/channels/<name>/settings.py`.
5. Register factory in `microclaw/channels/<name>/fabric.py`.

### Adding a New Storage Backend
1. Define interface in `sessions_storages/interfaces.py` (or `users_storages/`).
2. Implement in `sessions_storages/<backend>/storage.py`.
3. Add settings model and register in `fabric.py`.

### Configuration Changes
- Always add sensible defaults in `MicroclawSettings` or relevant settings class.
- Validate cross-references in `@model_validator(mode="after")`.
- Document new env vars and YAML keys.

## Security Checklist

- [ ] No hardcoded secrets in YAML/Python files.
- [ ] Secrets loaded via `!env` or `!include`.
- [ ] Sensitive files (`.env`, `config.yaml` with secrets) in `.gitignore`.
- [ ] Logs do not contain API keys, tokens, passwords.
- [ ] File paths sanitized to prevent traversal.
- [ ] User input validated via Pydantic.
- [ ] Toolkit sensitive operations use `PermissionModeEnum.REQUEST`.

## Common Commands

```bash
# Run tests
pytest

# Lint
ruff check .
ruff format .

# Run service
python -m microclaw run --config config.yaml --env .env

# Run channel directly
python -m microclaw channels telegram
python -m microclaw channels cli
```

---

This document is derived from `.ai/` internal docs, source code, and project conventions. Keep it updated when architecture or conventions change.
