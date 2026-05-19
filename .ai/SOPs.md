# Microclaw Standard Operating Procedures (SOPs)

## Coding Standards & Conventions

### General Python Standards

#### Type Hints
- **Always use type hints** for function parameters and return values
- Use `typing | None` instead of `Optional[...]` (Python 3.10+)
- Use `typing |` syntax for unions (Python 3.10+)
- Import from `typing` when needed: `list[Type]`, `dict[Key, Value]`, `AsyncGenerator`
- Use Self for instance methods returning self:

```python
from typing import Self, AsyncGenerator

async def get_messages(self) -> AsyncGenerator[Message, None]:
    async for message in self._storage:
        yield message

def chain_methods(self) -> Self:
    return self
```

#### Async/Await Patterns
- **All I/O operations MUST be async**
- Use `asyncio` library for async operations
- Use `aiofiles` for file I/O instead of built-in `open()`
- Use `apscheduler` async scheduler for cron tasks
- Never mix sync and async operations

```python
# ✅ Correct
async def get_data(self) -> dict:
    async with aiofiles.open("data.json") as f:
        return json.loads(await f.read())

# ❌ Wrong
def get_data(self) -> dict:
    with open("data.json") as f:
        return json.load(f)
```

#### Pydantic Models
- **Use Pydantic for all data structures**
- Use PydanticSettings for configuration
- Use Field() with descriptions for complex fields
- Use field_validator and field_serializer for custom logic
- Use models for both configuration and DTOs

```python
from pydantic import BaseModel, Field, field_validator

class AgentMessage(BaseModel):
    role: str = Field(description="Message role: user/assistant/system/tool")
    text: str | None = None
    spending: Spending | None = None
```

## Naming Conventions

### File and Directory Names
- **Snake_case** for Python files: `agent.py`, `channel.py`, `toolkit.py`
- **Modules directories**: Use snake_case, include `__init__.py`
- **Template files**: Use descriptive names with `.j2` extension: `agent_prompt.j2`
- **Test files**: Use `test_` prefix (when tests added)

### Variable and Function Names
- **Snake_case** for functions and variables: `get_agent()`, `user_session`
- **CamelCase** for constants: `MAX_TOKENS`, `DEFAULT_TIMEOUT`
- **Underscore prefix** for internal/private attributes: `_settings`, `_agent`
- **Double underscores** for dunder methods only: `__init__`, `__str__`

```python
class MyService:
    MAX_RETRIES = 3  # Constant
    
    def __init__(self, config: Config):
        self._config = config  # Internal
        self._cache = {}  # Internal
    
    async def get_data(self) -> dict:  # Public method
        return await self._fetch_data()
    
    async def _fetch_data(self) -> dict:  # Private method
        pass
```

### Class Names
- **PascalCase** for classes: `Agent`, `BaseChannel`, `MemoryToolkit`
- **Abstract classes**: Prefix with `Base`: `BaseChannel`, `BaseToolKit`
- **Interface classes**: Suffix with `Interface`: `SessionsStorageInterface`
- **Exception classes**: Suffix with `Exception`: `UserDeniedAction`

### Method Names
- **Verbs for actions**: `get_agent()`, `create_session()`, `update_task()`
- **Booleans**: Use `is_`, `has_`, `should_` prefixes: `is_admin()`, `has_permission()`
- **Async methods**: Use `async def` prefix, no special naming needed
- **Callback methods**: Use `on_` prefix: `on_chat_model_start()`, `on_tool_error()`

```python
class Agent:
    def is_ready(self) -> bool:
        return self._initialized
    
    async def should_summarize(self) -> bool:
        return await self._check_threshold()
    
    async def on_message_received(self, message: str):
        pass
```

### Configuration Keys
- **Snake_case** for YAML keys: `sessions_storage`, `allow_from`, `max_tool_calls`
- **Environment variables**: UPPER_CASE with prefix: `MICROCLAW_API_KEY`
- **Storage keys**: Use type prefixes: `session:{uuid}`, `user:{uuid}`, `confirm:{uuid}`

## Implementation Rules

### Component Architecture Rules

#### 1. Interface-First Design
- Always define abstract interfaces before implementations
- Use `Protocol` or abstract base classes for interfaces
- Implement concrete classes after interfaces are defined
- This ensures compatibility across storage backends

```python
# Interface first
class SessionsStorageInterface(abc.ABC):
    @abc.abstractmethod
    async def create_session(self, session_id: UUID) -> None:
        pass

# Implementation later
class FilesystemSessionsStorage(SessionsStorageInterface):
    async def create_session(self, session_id: UUID) -> None:
        pass
```

#### 2. Dependency Injection Pattern
- **NEVER** instantiate dependencies directly in components
- Always receive dependencies via constructor/method parameters
- Use DependencyResolver for complex resolution logic
- This enables testing and flexibility

```python
# ✅ Correct - Dependency injection
class Agent:
    def __init__(self, 
                 model_client: ModelClient,
                 toolkits: dict[str, BaseToolKit],
                 storage: SessionsStorageInterface):
        self._client = model_client
        self._toolkits = toolkits

# ❌ Wrong - Direct instantiation
class Agent:
    def __init__(self):
        self._client = ChatOpenAI(model="gpt-4")  # Bad!
```

#### 3. Service Mixin Pattern
- Extend `facets.AsyncioServiceMixin` for long-running services
- Implement `start()` and `stop()` methods
- Use `self.add_task()` for background tasks
- Services should self-register dependencies

```python
class MyChannel(facet.AsyncioServiceMixin):
    async def start(self):
        await self._connect()
        self.add_task(self._listen())
    
    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]:
        return [self._storage, self._syncer]
```

#### 4. Configuration-Driven Behavior
- **ONLY** use code defaults for critical settings
- All customizable behavior must be in configuration
- Use `Field(default_factory=Type)` for complex defaults
- Validate configuration at startup

```python
# ✅ Correct - Configuration driven
class AgentSettings(BaseModel):
    max_tool_calls: int = Field(default=25, ge=1, le=1000)
    temperature: float | None = None

# ❌ Wrong - Hardcoded behavior
class Agent:
    MAX_TOOL_CALLS = 25  # Should be in config!
```

### Error Handling Standards

#### Exception Strategy
- **Log errors with context**: Always include relevant data in error messages
- **Never expose stack traces to end users**: Return user-friendly messages
- **Use specific exception types**: Don't just raise `Exception`
- **Handle expected errors gracefully**: Network errors, file permissions, etc.

```python
# ✅ Correct error handling
async def create_session(self) -> Session:
    try:
        session = await self._storage.create()
        return session
    except PermissionError as e:
        logger.error(f"Permission denied creating session: {e}")
        raise PermissionDenied("Cannot create session - insufficient permissions")
    except OSError as e:
        logger.error(f"Filesystem error creating session: {e}")
        raise StorageError("Failed to create session")

# ❌ Wrong error handling
async def create_session(self):
    await self._storage.create()
```

#### Tool Error Handling
- Wrap tool calls in try/except
- Return errors as ToolMessage with traceback
- Use `_handle_tool_errors()` middleware
- Allow agent to retry or handle errors

```python
@wrap_tool_call
async def _handle_tool_errors(request, handler) -> Any:
    try:
        return await handler(request)
    except BaseException as exception:
        tb = "".join(traceback.format_exception(...))
        return ToolMessage(
            content=f"Tool error: {exception}\n\nTraceback:\n{tb}",
            tool_call_id=request.tool_call["id"],
        )
```

### Logging Standards

#### Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: Normal operation, lifecycle events
- **WARNING**: Unexpected but recoverable issues
- **ERROR**: Errors that need investigation
- **CRITICAL**: System-threatening errors

#### Log Format
- Use contextual loggers: `logger = logging.getLogger(__name__)`
- Include relevant data in log messages
- Use structured logging for complex data
- Never log sensitive information

```python
# ✅ Correct logging
logger.info("Starting session", extra={"session_id": str(session_id)})
logger.error("Failed to process message", exc_info=True, 
             extra={"message_id": str(message.id)})

# ❌ Wrong logging
logger.info("Processing message...")
logger.error(f"API Key: {api_key}")  # NEVER log secrets!
```

### Storage Standards

#### Filesystem Storage
- Use `aiofiles` for async file operations
- Use JSON format for readability
- Include locking for concurrent access
- Use UUID filenames for sessions/users

```python
async def save_session(self, data: SessionData):
    async with aiofiles.open(f"{session_id}.json", "w") as f:
        await f.write(data.model_dump_json(indent=2))
```

#### Database Storage
- Use SQLModel for ORM
- Use Alembic for migrations
- Always create migrations backwards-compatible
- Use transactions for multi-step operations

```python
class Session(BaseModel, table=True):
    __tablename__ = "sessions"
    id: UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    messages: list[AgentMessage] = Field(default_factory=list)
```

#### Memory Storage
- Use for testing only
- Not for production use
- No persistence after restart
- May have memory leaks with large datasets

### API Development Standards

#### REST API Rules
- **FastAPI** framework only
- Use Pydantic models for request/response
- Use `app.include_router()` for modular routes
- Implement proper HTTP status codes
- Include OpenAPI documentation

```python
@app.post("/sessions", response_model=SessionDTO)
async def create_session(
    request: CreateSessionRequest,
    storage: SessionsStorageInterface = Depends(get_storage)
):
    session_id = await storage.create_session()
    return SessionDTO(id=session_id)
```

#### Channel Implementation Rules
- Extend `BaseChannel` for all channels
- Implement `start_conversation()` method
- Implement `request_confirmation()` if user interaction needed
- Use channel-specific toolkit for channel tools
- Implement printer/formatter for message display

### Testing Standards (Future)

#### Unit Test Rules
- Use `unittest` or `pytest` framework
- Mock external dependencies (LLM, MCP, network)
- Test both happy path and error cases
- Test async code with async test functions

#### Integration Test Rules
- Test storage backends with real backend
- Test channels with mock agents
- Use test databases, filesystems
- Clean up after tests

```python
# Future test pattern
async def test_agent_summarization():
    agent = Agent(settings=test_settings, ...)
    messages = create_test_messages()
    summary = await agent.summarize_dialogue(messages)
    assert summary.is_summary is True
    assert summary.text is not None
```

### Security Standards

#### Sensitive Data Handling
- **NEVER** commit API keys, passwords, tokens to git
- Use environment variables: `!env TAG` in YAML
- Use `!include` to load secrets from separate files
- Add secrets files to `.gitignore`
- Mask sensitive data in logs

```yaml
# ✅ Correct - Environment variable
api_key: !env OPENAI_API_KEY

# ❌ Wrong - Hardcoded
api_key: "sk-proj-abcdef123456"
```

#### Input Validation
- Validate all user input using Pydantic
- Sanitize file paths to prevent directory traversal
- Validate message lengths and formats
- Use field validators for custom validation

```python
class Message(BaseModel):
    text: str = Field(max_length=10000)
    
    @field_validator("text")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        # Remove dangerous characters
        return value.strip()
```

#### Permission Rules
- Implement permission checks in toolkits
- Use PermissionModeEnum (ALLOW/REQUEST/DENY)
- Default to DENY mode for write operations
- Allow ALLOW mode for read-only operations

```python
@tool
async def create_task(self, name: str) -> Task:
    if self.settings.write_mode == PermissionModeEnum.DENY:
        raise PermissionError("Write operations denied")
    
    if self.settings.write_mode == PermissionModeEnum.REQUEST:
        if not await self.request_confirmation(f"Create task {name}?"):
            raise UserDeniedAction()
    
    return await self._client.create_task(name)
```

### Code Organization

#### Module Import Order
```python
# 1. Standard library imports
import asyncio
from typing import Self

# 2. Third-party imports
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

# 3. Local imports
from microclaw.agents import Agent
from microclaw.dto import AgentMessage
from .settings import ChannelSettings
```

#### File Template Pattern
```python
"""Module docstring describing purpose."""

import RelatedLibrary
from . import LocalImports

# Constants
CONSTANT_VALUE = "value"

# Classes
class MyClass:
    """Class docstring."""
    
    # Dunder methods
    def __init__(self, param: str):
        """Initialize class."""
        self._param = param
    
    def __repr__(self):
        return f"MyClass({self._param!r})"
    
    # Public methods
    async def public_method(self) -> ReturnType:
        """Public method docstring."""
        pass
    
    # Private methods
    async def _private_method(self) -> None:
        """Private method docstring."""
        pass

# Module-level functions
async def module_function() -> ReturnType:
    """Function docstring."""
    pass
```

### Documentation Standards

#### Docstring Format
- **Module docstring**: One-line summary at top of file
- **Class docstring**: One-line summary
- **Method docstring**: One-line summary, Args:, Returns: (for complex methods)
- **Tool docstrings**: Used for agent understanding, must be clear

```python
async def get_messages(
    self, 
    session_id: UUID, 
    last: int | None = None
) -> AsyncGenerator[AgentMessage]:
    """Get messages from session.
    
    Args:
        session_id: Unique session identifier
        last: Limit to last N messages, None for all
        
    Yields:
        AgentMessage objects in chronological order
    """
    pass
```

#### Code Comments
- **WHY** not **HOW**: Explain reasoning, not obvious code
- Keep comments short and relevant
- Update comments when code changes
- Prefer self-documenting code over comments

```python
# ✅ Good comment - explains reasoning
# We use recursion limit of 1000 because nested subagent calls can be deep
config = {"recursion_limit": 1000}

# ❌ Bad comment - states obvious
# This sets recursion limit to 1000
config = {"recursion_limit": 1000}
```

## Development Workflow

### Before Writing Code
1. **Read existing code**: Understand patterns used in similar components
2. **Check for existing implementations**: Don't reinvent functionality
3. **Design first**: Plan architecture, interfaces, dependencies
4. **Configuration-first**: Define config schema before implementation

### During Development
1. **Follow existing patterns**: Use same structures, naming, conventions
2. **Type everything**: Add type hints for all functions and variables
3. **Error handling**: Think about what can go wrong and handle it
4. **Logging**: Add appropriate log statements for operations

### Before Committing
1. **Run linting**: Use configured linter (Ruff)
2. **Test manually**: Verify functionality works as expected
3. **Review configuration**: Ensure settings are properly validated
4. **Update documentation**: Update relevant docstrings and comments

### Code Review Checklist
- [ ] Follows naming conventions
- [ ] Uses proper async/await patterns
- [ ] Has type hints everywhere
- [ ] Handles errors appropriately
- [ ] Logs important operations
- [ ] Uses dependency injection
- [ ] Configuration-driven where appropriate
- [ ] Documentation is clear
- [ ] No hardcoded secrets
- [ ] Tests included (when applicable)

## Technology-Specific Rules

### LangChain Integration
- Use `create_agent()` for agent creation
- Use `LangChainStructuredTool` for tools
- Use `agent.astream_events()` for streaming
- Implement middleware for error handling
- Use proper message types: `HumanMessage`, `AIMessage`, `SystemMessage`

### Pydantic Integration
- Use `Field()` for complex parameter definitions
- Use custom validators for validation logic
- Use `@model_validator` for cross-field validation
- Use `model_dump(mode="json")` for serialization
- Use `model_validate_json()` for deserialization

### FastAPI Integration
- Use `Depends()` for dependency injection
- Use `Response` types for custom responses
- Use `status` codes for HTTP status
- Use `APIRouter` for modular routing
- Include OpenAPI docs for all endpoints

### Aiogram Integration
- Use router/dispatcher pattern
- Implement middleware for message filtering
- Use FSM for conversation state
- Use inline keyboards for confirmations
- Implement typing status for better UX

## Anti-Patterns to Avoid

### ❌ Common Mistakes
1. **Direct instantiation**: Don't create dependencies manually
2. **Global state**: Avoid module-level variables that change
3. **Blocking I/O**: Never use sync operations in async code
4. **Hardcoded values**: Put everything in configuration
5. **No error handling**: Always handle potential failures
6. **Giant methods**: Break down complex logic into smaller methods
7. **Unused imports**: Clean up imports before committing
8. **Print debugging**: Use `logger.debug()` instead of `print()`

### ❌ Security Mistakes
1. **Hardcoded secrets**: Never commit credentials
2. **SQL injection**: Always use parameterized queries
3. **Path traversal**: Validate and sanitize file paths
4. **Information leak**: Don't expose errors to users
5. **Missing validation**: Always validate user input

### ❌ Performance Mistakes
1. **N+1 queries**: Batch operations where possible
2. **Inefficient loops**: Avoid nested async calls
3. **Unnecessary serialization**: Cache parsed data
4. **Blocking operations**: Use async alternatives
5. **No connection pooling**: Reuse connections

### ❌ Architecture Mistakes
1. **Circular dependencies**: Design to avoid import cycles
2. **Tight coupling**: Use interfaces and dependency injection
3. **God classes**: Split large classes into focused components
4. **Violation of SRP**: Make each class have one responsibility
5. **No separation of concerns**: Keep layers distinct

## Checklist for New Features

### Planning Phase
- [ ] Understand business requirements
- [ ] Review existing similar features
- [ ] Design API and interfaces
- [ ] Define configuration structure
- [ ] Plan error handling

### Implementation Phase
- [ ] Create interfaces first
- [ ] Implement configuration schemas
- [ ] Implement dependency injection
- [ ] Add type hints everywhere
- [ ] Add appropriate logging
- [ ] Handle errors gracefully
- [ ] Add documentation

### Testing Phase
- [ ] Manual testing of happy path
- [ ] Manual testing of error cases
- [ ] Test with different configurations
- [ ] Test resource cleanup
- [ ] Test edge cases

### Integration Phase
- [ ] Update configuration examples
- [ ] Update documentation
- [ ] Add to dependency resolver
- [ ] Register in service
- [ ] Update feature master list

## Continuous Improvement

### Code Quality Metrics
- Type hint coverage: Target 100%
- Docstring coverage: Target 100% for public APIs
- Error handling: All code paths should handle errors
- Test coverage: Target 80%+ (when tests added)

### Performance Targets
- Agent response < 5s for simple queries
- Session storage operations < 100ms
- Toolkit execution < 2s (excluding API calls)
- Startup time < 10s for default config

### Maintainability Goals
- < 50 lines per method (complexity management)
- < 5 parameters per function (parameter object preferred)
- < 3 levels of nesting (early returns preferred)
- Clear separation of concerns

---

**Remember**: These SOPs are living documents. Update them as patterns evolve and new best practices emerge in the codebase.