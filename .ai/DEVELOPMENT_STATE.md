# Microclaw Development State

## Current State & Progress

### Last Completed Tasks
1. **Multi-user Architecture Implementation** ✅
   - Complete user isolation system
   - User-specific agent configurations
   - Unified storage interfaces for sessions/users
   - Filesystem and Database storage implementations

2. **Subagent System** ✅
   - SubAgentToolKit for agent delegation
   - Configurable max_turns and summarization thresholds
   - Integration with main agent tool ecosystem
   - Nested subagent support

3. **Permission & Confirmation System** ✅
   - ALLOW/REQUEST/DENY permission modes
   - Cross-instance synchronization via Syncer
   - ConfirmationMixin for channel implementations
   - UserDeniedAction exception handling

4. **Automatic Summarization** ✅
   - Dialogue summarization at 80% context threshold
   - Memory flush with daily/general separation
   - Memory summarization when size exceeded
   - Integration with cron tasks for daily processing

5. **Streaming Responses** ✅
   - Real-time message streaming from LLM
   - Chunked message grouping
   - Streaming printer implementations for CLI and Telegram

6. **Storage Backend Implementation** ✅
   - FilesystemStorage (JSON-based)
   - DatabaseStorage (SQLModel/SQLAlchemy)
   - MemoryStorage (testing)
   - Async-optimized with proper locking

7. **MCP Protocol Support** ✅
   - MultiServerMCPClient integration
   - HTTP/WebSocket and local stdio transports
   - Tool discovery and integration
   - Configuration via YAML

8. **Cron Task System** ✅
   - APScheduler integration
   - System and user-defined cron tasks
   - FlushToMemory and SummarizeDialogues built-in tasks
   - User cron management via toolkit

9. **REST API** ✅
   - FastAPI implementation
   - Session and User endpoints
   - Dependency injection for auth/storage
   - OpenAPI documentation

## Known Issues

### Current TODO Items
1. **CLI Channel TUI Migration** 🔄
   - Status: In TODO list
   - Target: Migrate CLI channel to Textual TUI framework
   - Current: CLI channel exists but needs improvement
   - Priority: Medium

2. **Subagent Usage** ⚠️
   - Status: Agents don't use subagents
   - Problem: Subagent system implemented but not utilized by default agents
   - Expected: Agents should delegate specific tasks to subagents
   - Priority: High

### Feature Gaps
1. **Transaction Management**
   - File `transaction_manager.py` - Transaction manager implementation
   - Purpose unclear, needs integration or removal

2. **Matrix Channel**
   - Configured in pyproject.toml dependencies
   - Not implemented in channels/

3. **A2a Integration**
   - Configured in pyproject.toml dependencies  
   - Not implemented in main codebase

## Technical Debt

### Performance
- Agent caching: Caches resolved agents but no cache invalidation strategy
- Token estimation: TikToken used but no memoization for repeated calculations
- Filesystem storage: Reads entire session file for each query (could be optimized)

### Testing
- No unit test coverage
- No integration tests
- Manual testing only
- No CI/CD pipeline

### Documentation
- Some template files not documented (agent_prompt.j2 structure)
- Internal DTOs not fully documented
- Configuration examples incomplete

### Error Handling
- Tool errors returned as ToolMessage but no error recovery strategy
- Confirmation timeout not implemented (infinite wait)
- Connection errors not handled gracefully (MCP, databases)

### Code Quality
- Large methods (Agent.ask is 200+ lines)
- Some hardcoded values (polling intervals, timeouts)
- Inconsistent error messages
- Missing type hints in some utility functions

## Immediate Next Steps

### Priority 1: Critical Issues
1. **Fix Subagent Usage** ⚠️
   - Modify agent prompts to encourage subagent use
   - Add examples of subagent delegation in agent identity
   - Configuration: Extend agent identity descriptions
   - Testing: Create test case for subagent tool execution

2. **CLI TUI Migration** 🔄
   - Migrate to Textual framework
   - Improve user experience over current implementation
   - Maintain existing functionality
   - Target: Complete before v0.2.0

### Priority 2: Technical Improvements
1. **Transaction Manager Integration**
   - Determine purpose of `transaction_manager.py`
   - Integrate or remove
   - Document decision

2. **Error Handling Enhancement**
   - Add confirmation timeout with pickup
   - Implement retry logic for MCP connections
   - Graceful degradation when storage unavailable

3. **Performance Optimization**
   - Add token counting cache
   - Implement partial session reads
   - Add agent cache invalidation

### Priority 3: Feature Development
1. **Additional Channels**
   - Implement Matrix channel (dependencies exist)
   - Consider Slack, Discord channels
   - Generic HTTP webhook channel

2. **Advanced Features**
   - More sophisticated memory retrieval (semantic search)
   - Conversation branches/sharing
   - Multi-agent collaboration (beyond subagents)

3. **Monitoring & Analytics**
   - Performance metrics collection
   - Conversation analytics
   - Cost tracking dashboards

## Version Roadmap

### v0.1.0 - Foundation ✅ (Complete)
- Multi-user architecture
- Subagent system
- Automatic summarization
- Permission system
- Storage backends (filesystem, database)
- MCP support
- Cron tasks
- REST API
- CLI and Telegram channels

### v0.2.0 - Polish ⏳ (Next)
- CLI TUI migration
- Subagent usage improvement
- Error handling enhancements
- Performance optimizations
- Documentation updates
- Test coverage (basic)

### v0.3.0 - Expansion 🔮 (Future)
- Additional channels (Matrix, etc.)
- Advanced memory (semantic search)
- Multi-agent collaboration
- Monitoring/analytics
- Web UI interface
- Plugin marketplace

## Development Standards

### Code Organization
- Use Type Hints consistently
- Prefer async/await over synchronous code
- Use Pydantic models for all data structures
- Follow existing patterns for new components

### Configuration
- All settings via YAML configuration
- Environment variables via !env tag
- Include support for !include tag
- Validate configuration at startup

### Error Handling
- Log errors with context
- Return user-friendly error messages
- Never expose stack traces to end users
- Implement graceful degradation

### Performance
- Minimize blocking I/O operations
- Use connection pooling for databases
- Cache frequently accessed data
- Profile before optimizing

### Testing (Future)
- Unit tests for business logic
- Integration tests for storage backends
- E2E tests for complete workflows
- Mock external dependencies (LLM, MCP)

### Security
- Validate all user input
- Sanitize file paths
- Rate limit API calls
- Never log sensitive data (API keys, passwords)
- Use environment variables for secrets

## Configuration File State

### Current config.yaml Analysis
- **Providers**: Cloud.ru configured with API key (⚠️ should be in environment)
- **Models**: Qwen3-Coder-Next and Whisper configured
- **Toolkits**: Personal integration (calendar, tasks, contacts, files, email, homeassistant)
- **Agents**: personal_assistant, butler, travel_agent configured
- **Channels**: Telegram only configured
- **Crons**: Morning briefing task at 02:17 daily

### Security Concerns
⚠️ **CRITICAL**: API keys hardcoded in config.yaml
- Cloud.ru API key: Visible in plain text
- Nextcloud credentials: Visible in plain text  
- Email credentials: Visible in plain text
- HomeAssistant token: Visible in plain text
- Telegram bot token: Visible in plain text
- Discogs token: Visible in plain text

**Recommendation**: Move all sensitive data to environment variables

### Functional Status
- ✅ Personal assistant working
- ✅ Task management via Nextcloud Tasks
- ✅ Calendar via CalDAV
- ✅ Email configuration multiple accounts
- ✅ HomeAssistant integration
- ✅ Telegram polling mode
- ✅ Morning briefing cron job
- ❌ Subagent delegation (not utilized)
- ❌ REST API (not configured)
- ❌ Webhooks (not configured)

## Database Schema

### Current State
- SQLModel models defined in `api/rest/sessions/` and `api/rest/users/`
- Alembic migrations configured but no migrations found
- Database support implemented but SQLite default

### Schema Changes Pending
- Add sessions table (UUID, messages_json, context_size, spending_json)
- Add users table (id, role, agent_config_json)
- Add cron_tasks table (id, path, cron, enabled, args_json)
- Implement timezone support for scheduling

## Deployment Status

### Development Environment
- ✅ Python 3.13+ environment
- ✅ Virtual environment configured
- ✅ Dependencies installed (uv.lock)
- ✅ Configuration file present

### Production Readiness
- ❌ Environment variables not used
- ❌ No Docker/virtualization strategy
- ❌ No logging configuration
- ❌ No backup strategy for sessions/storage
- ❌ No monitoring/alerting
- ❌ No SSL/TLS configuration
- ❌ No rate limiting
- ❌ No authentication beyond channel-based

## Testing Status

### Manual Testing Results
- ✅ CLI channel basic functionality
- ✅ Telegram bot responses
- ✅ Tool execution (tasks, calendar, etc.)
- ✅ Session persistence
- ✅ Summarization triggers at threshold
- ❌ Subagent delegation
- ❌ REST API endpoints
- ❌ Database storage
- ❌ User permissions
- ❌ Cross-instance sync

### Automated Testing
- ❌ No unit tests
- ❌ No integration tests  
- ❌ No E2E tests
- ❌ No performance tests
- ❌ No load tests

## Dependencies State

### Critical Dependencies
- ✅ LangChain 1.2.10+ - Agent orchestration
- ✅ Pydantic 2.12.5+ - Data validation
- ✅ FastAPI 0.129.0+ - REST API
- ✅ Aiogram 3.25+ - Telegram integration
- ✅ APScheduler 3.10.4+ - Cron scheduling
- ✅ SQLModel 0.0.38+ - Database ORM
- ✅ Loguru 0.7.3+ - Logging
- ✅ Textual 8.2.5+ - CLI UI

### Optional/Unused Dependencies
- ❌Matrix dependencies configured but not used
- ❌ A2a dependencies configured but not used
- ⚠️ evolution-langchain - Cloud.ru specific
- ⚠️ langchain-ollama - Only if Ollama used
- ⚠️ mutagen - Only if audio tags used
- ⚠️ python3-discogs-client - Only if discogs used

## Community & Support

### Documentation
- ✅ FEATURES_ANALYSIS.md - Recent feature overview (Russian)
- ✅ TODO.md - Outstanding tasks
- ✅ Config examples in config.example.yaml
- ❌ No API documentation (REST API missing)
- ❌ No developer guide
- ❌ No contribution guidelines

### Issues & Bug Tracking
- No public issue tracker configured
- Git repository initialized
- 0 issues filed
- 0 pull requests

## Conclusion

The project has achieved a solid foundation with all major components implemented and functional. The immediate focus should be on:

1. **Security**: Move sensitive configuration to environment variables
2. **Subagent Usage**: Enable and test subagent delegation functionality
3. **CLI TUI**: Complete migration to Textual framework
4. **Testing**: Establish basic test coverage
5. **Documentation**: Create comprehensive developer and API documentation

The architecture is well-designed for scalability and extensibility, with clear separation of concerns and proper async patterns throughout.
