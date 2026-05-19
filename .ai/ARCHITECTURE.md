# Microclaw Architecture

## System Context Map

### Directory Structure & Module Responsibilities

```
microclaw/
├── agents/                    # Agent orchestration and management
│   ├── agent.py             # Core Agent class - LLM integration, streaming, summarization
│   ├── settings.py          # Agent, Model, Provider configurations
│   ├── subagents/           # Subagent delegation system
│   │   ├── toolkit.py       # SubAgentToolKit - calling subagents
│   │   └── settings.py      # SubAgentSettings configuration
│   ├── templates/           # Jinja2 templates for agent prompts
│   │   ├── agent_prompt.j2 # System prompt generator
│   │   ├── summarize_dialogue_prompt.j2
│   │   └── summarize_memory_prompt.j2
│   ├── dto.py               # Internal agent DTOs
│   └── cli.py               # CLI-specific agent implementations
│
├── channels/                  # Communication channels (user interfaces)
│   ├── base.py              # BaseChannel - abstract channel with confirmation system
│   ├── settings.py          # Channel configuration types
│   ├── fabric.py            # Channel factory (get_channel)
│   ├── utils.py             # Channel utilities (AgentMessageSaver)
│   ├── cli/                 # CLI channel implementation
│   │   ├── channel.py       # CLIChannel - Textual TUI interface
│   │   ├── ui.py            # CLI UI components
│   │   ├── printer.py       # Agent message display logic
│   │   └── settings.py      # CLI-specific settings
│   └── telegram/            # Telegram channel implementation
│       ├── base.py          # Telegram base channel
│       ├── polling/         # Long-polling implementation
│       │   ├── channel.py   # TelegramPollingChannel
│       │   └── settings.py  # Polling configuration
│       ├── webhook/         # Webhook implementation
│       │   ├── channel.py   # TelegramWebhookChannel
│       │   └── settings.py  # Webhook configuration
│       ├── middlewares/     # Telegram message processing
│       │   ├── auth.py      # User authorization middleware
│       │   ├── typing.py    # Typing status middleware
│       │   └── typing.py    # Message formatting
│       ├── toolkit/         # Telegram-specific tools
│       │   ├── toolkit.py   # Telegram toolkit for bot control
│       │   └── settings.py  # Telegram toolkit settings
│       ├── printer.py       # Telegram message formatting
│       ├── fabric.py        # Telegram channel factory
│       └── utils.py         # Telegram utilities
│
├── toolkits/                  # Agent capabilities/tools
│   ├── base.py              # BaseToolKit abstract class with @tool decorator
│   ├── enums.py             # PermissionModeEnum (ALLOW/REQUEST/DENY)
│   ├── settings.py          # ToolKitSettings configuration
│   ├── exceptions.py        # Domain exceptions (UserDeniedAction)
│   ├── memory/              # Memory management toolkit
│   │   ├── toolkit.py       # MemoryToolKit - long-term memory
│   │   └── drivers/         # Storage backends (filesystem, database)
│   ├── tasks/               # Task management (Nextcloud Tasks via CalDAV)
│   │   ├── toolkit.py       # TasksToolKit
│   │   ├── dto.py           # Task DTOs
│   │   └── settings.py      # Tasks configuration
│   ├── caldav/              # Calendar management
│   ├── carddav/             # Contact management  
│   ├── email/               # Email tools
│   ├── filesystem/          # File operations
│   ├── webdav/              # WebDAV file operations
│   ├── homeassistant/       # Home Assistant integration
│   ├── discogs/             # Discogs music metadata
│   ├── audio_tags/          # Audio file metadata
│   ├── command/             # Shell command execution
│   ├── user_crons/          # User-defined cron tasks
│   ├── cron/                # System cron tasks
│   └── dynamic_loader/      # Dynamic toolkit loading
│
├── sessions_storages/          # Session persistence layer
│   ├── interfaces.py        # SessionsStorageInterface abstract class
│   ├── filesystem/          # JSON file-based storage
│   │   ├── storage.py       # FilesystemSessionsStorage
│   │   ├── dto.py           # SessionData DTO
│   │   └── settings.py      # FS storage configuration
│   ├── database/            # SQLModel-based storage
│   │   └── storage.py       # DatabaseSessionsStorage
│   └── memory/              # In-memory storage (testing)
│
├── users_storages/            # User persistence layer
│   ├── interfaces.py        # UsersStorageInterface abstract class
│   ├── filesystem/          # JSON file-based user storage
│   ├── database/            # SQLModel-based user storage
│   └── memory/              # In-memory user storage
│
├── syncers/                   # Multi-instance synchronization
│   ├── interfaces.py        # SyncerInterface abstract class
│   └── memory/              # Redis-backed memory synchronization
│
├── stt/                       # Speech-to-Text integration
│   ├── base.py              # STT abstract class
│   └── provider/            # Provider-specific implementations
│
├── cron/                      # Scheduled task system
│   ├── base.py              # BaseCronTask abstract class
│   ├── settings.py          # CronTaskSettings
│   ├── tasks/               # Built-in cron tasks
│   │   ├── flush_to_memory.py
│   │   └── summarize_dialogues.py
│   └── factory.py           # Cron task factory
│
├── api/                       # REST API layer
│   └── rest/                # FastAPI implementation
│       ├── router.py         # Main API router
│       ├── settings.py       # REST API configuration
│       ├── service.py        # API service logic
│       ├── sessions/         # Session endpoints
│       │   └── router.py    # /sessions endpoints
│       ├── users/            # User endpoints
│       │   ├── router.py    # /users endpoints  
│       │   ├── handlers.py  # Request handlers
│       │   ├── schemas.py   # Request/response DTOs
│       │   └── dependencies.py # FastAPI dependencies
│       └── dependencies.py   # API-wide dependencies
│
├── utils/                     # Utility modules
│   ├── database/            # Database utilities
│   └── helpers.py           # General helpers (get_by_key_or_first)
│
├── dto.py                     # Shared data models
│   ├── AgentMessage         # Message structure
│   ├── Spending             # Token/cost tracking
│   ├── User                 # User model
│   ├── CronTask             # Cron task model
│   └── Permission enums     # Role/permission enums
│
├── settings.py                # Main configuration loader
│   ├── MicroclawSettings    # Root configuration class
│   ├── LoggingSettings      # Logging configuration
│   └── YAML loaders         # !include, !env tags support
│
├── resolver.py                # Dependency injection container
│   ├── DependencyResolver   # Main resolution logic
│   ├── Agent resolution     # resolve_agent, resolve_subagents
│   ├── Channel resolution   # resolve_channel
│   ├── Toolkit resolution   # resolve_toolkits
│   └── Storage resolution   # resolve_sessions_storage, resolve_users_storage
│
├── service.py                # Core service manager
│   └── MicroclawService     # Main service orchestratior
│
├── cli.py                    # CLI entry point
│   └── get_cli()             # Typer CLI application
│
└── __main__.py              # Module entry point

```

## Dependency & State Graph

### Component Dependencies

```
MicroclawService
├── DependencyResolver
│   ├── Providers (API endpoints)
│   ├── Models (LLM configurations)
│   ├── Toolkits (tools)
│   │   └── BaseToolKit implementations
│   ├── Channels (user interfaces)
│   │   ├── CLIChannel
│   │   └── TelegramChannel
│   ├── Agents (LLM integration)
│   │   ├── LangChain Agent
│   │   ├── MCP Client (MultiServerMCPClient)
│   │   └── SubAgentToolKits
│   ├── SessionsStorage (persistence)
│   │   ├── FilesystemSessionsStorage
│   │   └── DatabaseSessionsStorage
│   ├── UsersStorage (user management)
│   │   ├── FilesystemUsersStorage
│   │   └── DatabaseUsersStorage
│   ├── Syncer (multi-instance sync)
│   │   └── MemorySyncer (Redis)
│   ├── STT (speech recognition)
│   └── CronTasks (scheduled jobs)
│
├── Facet.AsyncioServiceMixin (lifecycle management)
└── Configuration (YAML + Environment)

Agent Dependencies:
├── Model Client (LangChain wrappers)
│   ├── ChatOpenAI (OpenAI API)
│   ├── EvolutionInference (Cloud.ru)
│   └── ChatOllama (Ollama)
├── Toolkits
│   ├── Memory, Tasks, Email, etc.
│   └── ChannelToolkit (channel-specific tools)
├── MCP Tools (MultiServerMCPClient)
└── SubAgentToolKits (delegation)

Channel Dependencies:
├── BaseChannel
│   ├── ConfirmationMixin (user confirmations)
│   ├── SessionManager
│   └── ContextVars (current channel tracking)
├── SessionsStorage (dialog history)
├── UsersStorage (user data)
├── Syncer (cross-instance sync)
└── Agent (LLM integration)
```

### State Management

1. **Session State**:
   - Stored in SessionsStorage (filesystem/database)
   - Contains: messages, spending, context size
   - Key: session_id (UUID)

2. **User State**:
   - Stored in UsersStorage (filesystem/database)
   - Contains: user_id, role, agent configuration
   - Key: channel_key + channel_internal_id

3. **Memory State**:
   - Stored in MemoryToolkit drivers
   - Contains: general memory, daily memories
   - Key: date + memory_type

4. **Sync State**:
   - Stored in Syncer (Redis)
   - Contains: confirmations, cross-instance data
   - Key: sync_key (strings like "confirm:{uuid}")

5. **Agent State**:
   - Cached in DependencyResolver
   - Contains: instantiated Agent objects
   - Key: agent_name

### Data Flow

**Message Processing Flow**:
```
User Input (Channel)
    ↓
Create AgentMessage (role='user')
    ↓
Store in SessionsStorage
    ↓
Load conversation history
    ↓
Agent.ask() (LLM invocation)
    ↓
Tool Execution (if needed)
    ├── Toolkit.get_tools()
    ├── SubAgentToolKit.call_agent()
    └── MCP.get_tools()
    ↓
Streaming Response
    ↓
AgentMessageSaver (log messages)
    ↓
Channel output (display)
    ↓
Check context threshold
    ↓
Summarize if needed
    ├── Agent.summarize_dialogue()
    ├── MemoryToolkit.append_to_memory()
    └── Agent.summarize_memory()
```

**Subagent Delegation Flow**:
```
Agent calls subagent tool
    ↓
SubAgentToolKit.call_agent()
    ↓
Create new subagent instance
    ↓
Execute subagent with max_turns limit
    ↓
Collect all messages from subagent conversation
    ↓
Summarize if exceeds threshold
    ↓
Return summary to main agent
```

**Cron Task Execution Flow**:
```
APScheduler trigger
    ↓
BaseCronTask.execute() (async)
    ↓
Get users from UsersStorage
    ↓
Get user sessions from SessionsStorage
    ↓
Agent.summarize_dialogue() / extract_important_info()
    ↓
MemoryToolkit.append_to_memory()
```

## API & Interface Definitions

### Core Interfaces

**SessionsStorageInterface**:
```python
async def create_session(session_id: UUID) -> None
async def add_message(session_id: UUID, message: AgentMessage) -> None
async def get_messages(session_id: UUID, last: int | None = None, 
                      from_last_summarization: bool = True) -> AsyncGenerator[AgentMessage]
async def get_spending(session_id: UUID) -> Spending
async def get_context_size(session_id: UUID) -> int
```

**UsersStorageInterface**:
```python
async def create_user() -> User
async def get_user_by_channel(channel_key: str, 
                             channel_internal_id: str) -> User | None
async def attach_session_to_user(user_id: UUID, session_id: UUID, 
                                channel_key: str, channel_internal_id: str) -> None
async def get_crons(user_id: UUID) -> list[CronTask]
```

**SyncerInterface**:
```python
async def set(key: str, value: Any) -> None
async def get(key: str) -> Any
async def delete(key: str) -> None
```

### Channel API

**BaseChannel**:
```python
async def start_conversation(session_id: UUID, channel_internal_id: int, 
                           new_messages: list[AgentMessage] | None = None,
                           agent: Agent | None = None) -> None
async def request_confirmation(question: str) -> UUID
async def wait_for_confirmation(confirmation_id: UUID) -> bool
async def summarize_dialog_if_needed(agent: Agent, session_id: UUID) -> bool
```

### Agent API

**Agent**:
```python
async def ask(messages: list[AgentMessage], channel: BaseChannel | None = None, 
             stream: bool = False) -> AsyncGenerator[AgentMessage]
async def summarize_dialogue(messages: list[AgentMessage], 
                            max_tokens: int = 300) -> AgentMessage
async def summarize_memory(old_context: str, new_context: str, 
                         max_tokens: int = 300, is_daily: bool = False) -> AgentMessage
async def extract_important_info(messages: list[AgentMessage], 
                                max_tokens: int = 300, is_daily: bool = False) -> str
def get_model_context_window_size() -> int | None
def get_context_threshold_size() -> float | None
def get_memory_toolkit() -> MemoryToolKit | None
```

### Toolkit API

**BaseToolKit**:
```python
@tool
async def tool_method(...) -> Any:  # Decorated methods become tools
    pass

def get_tools() -> list[LangChainStructuredTool]
async def request_confirmation(question: str) -> bool  # Permission check
```

### Data Structures

**AgentMessage**:
```python
role: str  # 'user', 'assistant', 'system', 'tool'
text: str | None
chunked_message_id: str | None  # For streaming
spending: Spending | None
is_summary: bool
audio: bytes | None
audio_format: str | None
```

**Spending**:
```python
input_tokens: int = 0
output_tokens: int = 0
cache_read_tokens: int = 0
cache_write_tokens: int = 0
audio_input_seconds: int = 0
audio_output_seconds: int = 0
cost: float = 0.0
currency: str = "$"
```

**User**:
```python
id: UUID
role: UserRoleEnum  # USER, ADMIN
agent: dict[str, Any] | None  # Agent configuration
```

**CronTask**:
```python
id: UUID
path: str  # Task class path
cron: str  # Cron expression
enabled: bool = True
args: dict[str, Any]
```
