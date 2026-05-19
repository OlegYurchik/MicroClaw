# Microclaw Core Logic

## Key Algorithms & Business Rules

### 1. Agent Conversation Flow

**Purpose**: Manage conversation with LLM including tool execution, streaming, and error handling

**Location**: `microclaw/agents/agent.py` - `Agent.ask()`

**Algorithm**:
1. Convert AgentMessage list to LangChain message format
2. Generate dynamic system prompt using Jinja2 template
3. Combine tools: toolkits + MCP tools + channel tools + subagent tools
4. Apply middleware: tool call limiting + tool error handling
5. Stream events from LangChain agent
6. Track tokens and costs per chunk
7. Yield streaming messages if requested, otherwise accumulate
8. Return spending summary at end

**Key Business Rules**:
- Max tool calls: 25 (configurable via `max_tool_calls`)
- Tool errors are caught and returned as ToolMessage with traceback
- Chunked messages grouped by `chunked_message_id`
- Streaming vs non-streaming behavior controlled by `stream` parameter
- Token counting uses tiktoken, falls back to cl100k_base encoding

### 2. Automatic Summarization System

**Purpose**: Manage token usage through intelligent dialogue and memory summarization

**Location**: `microclaw/channels/base.py` - `summarize_dialog_if_needed()`

**Algorithm**:
1. Check if summarization is enabled for agent
2. Calculate context threshold: `context_window_size * context_threshold_size` (default 80%)
3. Get current session context size from storage
4. If exceeded threshold:
   - Extract important info for long-term memory (if memory flush enabled)
   - Extract daily info for date-specific memory
   - Append to memory toolkit with date separation
   - Summarize entire dialogue (excluding existing summaries)
   - Store summary message in session
   - Reset context size to summary token count

**Key Business Rules**:
- Dialogue summarization threshold: 80% of context window (default)
- Memory flush enabled by default (`enable_memory_flush: true`)
- Max memory flush tokens: 10,000 (default)
- Memory size exceeded -> summarize old + new memory
- Summaries marked with `is_summary: true`
- Messages after last summary are included in next summarization

### 3. Subagent Delegation

**Purpose**: Allow agents to delegate specialized tasks to subagents with conversation limits

**Location**: `microclaw/agents/subagents/toolkit.py` - `SubAgentToolKit`

**Algorithm**:
1. User/main agent calls subagent tool
2. Create isolated conversation context for subagent
3. Execute subagent with specified max_turns
4. Collect all messages from subagent conversation
5. If conversation exceeds summarization threshold:
   - Summarize subagent conversation
   - Replace with summary
6. Return all messages (or summary) to main agent

**Key Business Rules**:
- Default max_turns: 10 (configurable)
- Channels/subagents can call tools without reconfirmation
- Subagent inherites main agent's permission mode
- Subagent tools prefixed with agent name (e.g., `butler_homeassistant`)
- Supports nested subagent calls (subagent calling another subagent)

### 4. Permission System

**Purpose**: Control agent tool execution through user confirmation system

**Location**: `microclaw/channels/base.py` - `ConfirmationMixin`

**Algorithm**:
1. Tool with `PermissionModeEnum.REQUEST` called
2. Toolkit calls `request_confirmation(question)` method
3. Channel generates confirmation_id (UUID)
4. Channel displays question to user (CLI modal, Telegram inline keyboard)
5. User approves/denies -> channel calls `resolve_confirmation(id, approved)`
6. Confirmation stored in syncer with key `confirm:{id}`
7. Original toolkit call waits in `wait_for_confirmation(id)` loop
8. Polls syncer every 0.1 seconds until result available
9. Returns boolean to toolkit
10. If denied -> raises `UserDeniedAction` exception

**Key Business Rules**:
- Three modes: ALLOW (no confirmation), REQUEST (ask user), DENY (block)
- Confirmation timeout: not implemented (infinite wait)
- Cross-instance sync: Uses Syncer for multi-instance deployments
- Tool error middleware catches UserDeniedAction and returns error message

### 5. Memory Management

**Purpose**: Maintain long-term memory with automatic summarization and date separation

**Location**: `microclaw/toolkits/memory/toolkit.py`

**Algorithm**:
**Reading Memory**:
1. Get memory for specific date or None (general memory)
2. Include general memory + today's memory + yesterday's memory in agent prompt
3. Each memory section labeled with date

**Writing Memory**:
1. Attempt to append to memory
2. If `MemorySizeExceeded` exception:
   - Get old memory content
   - Call `agent.summarize_memory(old_context, new_context, is_daily)`
   - Rewrite memory with summary
3. Separate daily memory (date-specific) from general memory

**Key Business Rules**:
- Daily memory: Date-specific information (today's events)
- General memory: Long-term information (user preferences, facts)
- Memory size limits prevent unbounded growth
- Automatic summarization when limits exceeded
- Yesterday's memory included in context for continuity

### 6. Token Counting & Cost Calculation

**Purpose**: Track token usage and compute costs for API calls

**Location**: `microclaw/agents/agent.py` - `_get_tokens_count()`, Spending class

**Algorithm**:
**Token Counting**:
1. Use tiktoken encoding for specific model
2. Fallback to cl100k_base if model not found
3. Count tokens for all text content (input messages, output chunks)

**Cost Calculation**:
1. Use model-specific costs: input, output, cache_read, cache_write, audio_input, audio_output
2. Costs per 1M tokens (default) or per 1 second (audio)
3. Formula: `cost = (tokens * rate / 1_000_000) + (audio_seconds * rate)`
4. Track per-session and cumulative spending

**Key Business Rules**:
- Audio costs calculated in seconds, text in tokens
- Supports caching costs (read/write) for models with context caching
- Currency configurable per model
- Spending tracked per message and aggregated per session

### 7. Session Persistence

**Purpose**: Reliable storage and retrieval of conversation history

**Location**: `microclaw/sessions_storages/filesystem/storage.py`

**Algorithm**:
1. Create session: Initialize SessionData with empty messages list
2. Add message: Append to messages list, update context size and spending
3. Get messages: Load entire session, slice from end (last N messages)
4. Find last summary: Iterate to find `is_summary: true`, start from there
5. Calculate context size: Sum tokens from last summary + subsequent messages

**Key Business Rules**:
- Files stored as `<session_id>.json` in configured directory
- Context size tracks tokens after last summary for threshold calculation
- Spending aggregated per session
- Per-session async lock prevents concurrent writes
- Global lock manages lock dictionary

### 8. User Session Management

**Purpose**: Link sessions to users across multiple channels

**Location**: `microclaw/channels/base.py` - `get_agent_for_user()`

**Algorithm**:
1. Look up user by channel credentials (telegram_id, etc.)
2. Check if user has custom agent configuration
3. If yes, resolve user-specific agent
4. If no, use channel's default agent
5. Cache resolved agent by user.id to avoid re-resolution
6. Provide user_id to cron tasks and memory operations

**Key Business Rules**:
- Users created automatically on first interaction
- User persists across sessions within same channel
- Each user can have personalized agent settings
- Agent configuration includes: model, toolkits, identity, subagents
- Role-based permissions: USER vs ADMIN

### 9. Task Scheduling (Cron)

**Purpose**: Execute automated tasks at scheduled times

**Location**: `microclaw/cron/`, `microclaw/resolver.py`

**Algorithm**:
**System Tasks**:
1. `FlushToMemoryCronTask`: Daily at 1 AM
   - Iterate all users
   - Get all user sessions
   - Extract important info from conversations
   - Append to memory toolkit

2. `SummarizeDialoguesCronTask`: 
   - Check all sessions for context threshold
   - Summarize if needed

**User Tasks**:
1. Load cron tasks from UsersStorage
2. Each task: path, cron expression, args
3. Enable/disable per task
4. Create BaseCronTask instances dynamically

**Key Business Rules**:
- System tasks always enabled (`cron: "0 1 * * *"`)
- User tasks can be disabled via `enabled: false`
- Task args passed to execute() method
- Tasks run in async context via APScheduler
- Support for dynamic language specs in cron expressions

### 10. MCP Tool Integration

**Purpose**: Integrate external tools via Model Context Protocol

**Location**: `microclaw/agents/agent.py` - `_create_mcp_client()`

**Algorithm**:
1. Parse MCP settings from configuration
2. For HTTP/websocket MCPs:
   - Set transport, URL
3. For local MCPs:
   - Set transport to "stdio"
   - Configure command and args
4. Create MultiServerMCPClient with server configurations
5. Load available tools from MCP servers
6. Combine with toolkit tools for agent

**Key Business Rules**:
- MCP tools prefixed with server name
- Supports both remote (HTTP/WS) and local (stdio) MCPs
- MCP tools treated like toolkit tools by LangChain agent
- No permission system for MCP tools (assume ALLOW mode)
- MCP connection established once per agent at initialization

### 11. Audio Processing Pipeline

**Purpose**: Handle voice input with speech-to-text and audio file limits

**Location**: `microclaw/stt/`, `microclaw/channels/`

**Algorithm**:
1. User sends audio file
2. Channel checks against `model_settings.audio_max_size`
3. If exceeds limit, reject with error message
4. Convert audio to base64
5. Call STT (whisper) model
6. Get text transcription
7. Process as regular text input
8. Track audio cost separately (per second vs per token)

**Key Business Rules**:
- Audio limit: 26,214,400 bytes (~25 MB default)
- Audio input supported only on models with `InputTypeEnum.AUDIO`
- Separate audio tokens/costs tracked in Spending
- Whisper large-v3 model used by default
- Support for multiple audio formats (MP3, WAV, etc.)

### 12. Configuration Resolution

**Purpose**: Resolve string references to configuration objects recursively

**Location**: `microclaw/settings.py`, `microclaw/resolver.py`

**Algorithm**:
1. Load YAML config with !include and !env tag support
2. Validate configuration links:
   - Model.provider -> Providers dict
   - Agent.model -> Models dict
   - Channel.agent -> Agents dict
   - Channel.sessions_storage -> Sessions_storages dict
3. Resolve to actual objects or raise ValueError
4. Support inline configuration (AgentSettings directly in channel)
5. Default fallback to "default" or first item if None

**Key Business Rules**:
- Configuration validation at startup
- Circular references detected and rejected
- Environment variables via !env TAG
- Include external files via !include TAG
- Type validation on all Pydantic models

## Critical Functions Reference

### Streaming Response Generation
`Agent.ask()` handles streaming with chunk grouping, token tracking, and tool execution middleware

### Context Management  
`BaseChannel.is_context_went_across_threshold()` checks token usage against 80% threshold

### Memory Summarization
`Agent.summarize_memory()` and `summarize_dialogue()` use Jinja2 templates with specific prompts

### Permission Enforcement
`ConfirmationMixin.request_confirmation()` and `wait_for_confirmation()` implement cross-instance consensus

### Tool Discovery
`Resolver.resolve_toolkits()` and `BaseToolKit.get_tools()` combine toolkits, MCP, channel, and subagent tools

### Session State
`FilesystemSessionsStorage._read_session()` and `_write_session()` handle atomic JSON serialization

### User Authentication
`Channels.telegram.middlewares.auth` middleware filters unauthorized users via `allow_from` setting

### Service Lifecycle
`MicroclawService` uses facets.AsyncioServiceMixin for correct startup/shutdown ordering of components

## Complex Business Rules

### Cross-Instance Consistency
- Syncer uses Redis for distributed confirmation and state sharing
- All instances read/write to same sessions/users storage for data consistency
- Agent caching per-user in resolver for performance

### Multi-Tenant Security
- Complete isolation between users (sessions, memory, cron tasks)
- User-specific agent configurations override channel defaults
- Admin role may have elevated permissions (not fully implemented)

### Resource Management
- Automatic summarization prevents memory/context leaks
- Per-session token limits and spending tracking
- Async locks prevent concurrent session corruption

### Error Recovery
- Tool errors caught and returned to agent vs crash
- UserDeniedAction exceptions handled gracefully
- Fallback tokenizers and model profiles for missing data

### Platform Compatibility
- Works with OpenAI, Cloud.ru, Ollama providers
- Supports Text and Audio input types
- Multiple storage backends (filesystem, database, memory)
- Extensible channel system (CLI, Telegram, custom)
