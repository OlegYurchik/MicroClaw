# Microclaw Project Context

## Project Blueprint

### Core Purpose
Microclaw is a **multi-user AI agent micro-framework** designed for building intelligent assistants with distributed architecture, comprehensive tool integration, and scalable session management. It transforms from a single-user assistant into a production-grade multi-user platform with permission systems, subagent delegation, and automatic summarization.

### Tech Stack
- **Language**: Python 3.13+
- **AI/ML**: 
  - LangChain (agent orchestration)
  - LangChain MCP Adapters (MCP protocol support)
  - OpenAI, Cloud.ru (Evolution), Ollama providers
  - TikToken (token counting)
- **Web/API**:
  - Aiogram 3.25+ (Telegram integration)
  - FastAPI (REST API)
  - Uvicorn (ASGI server)
- **Database**: 
  - SQLModel/SQLAlchemy 2.0.49+ (ORM)
  - Alembic (migrations)
- **Task Scheduling**: APScheduler 3.10.4+
- **File Processing**: aiofiles, aiodav, caldav, carddav
- **Configuration**: Pydantic 2.12.5+, PyYAML, Jinja2
- **Logging**: Loguru 0.7.3+
- **UI**: Textual 8.2.5+ (CLI interface)

### Architectural Patterns
1. **Service-Oriented Architecture (SOA)** - Channels, Agents, Storage as independent services
2. **Factory Pattern** - Dynamic resolution of components (DependencyResolver)
3. **Strategy Pattern** - Pluggable storage backends (Filesystem, Memory, Database)
4. **Plugin System** - Toolkits and MCP servers as extensible modules
5. **Middleware Pattern** - Channel middleware for auth, typing, message preprocessing
6. **Observer Pattern** - AsyncEvent system for service lifecycle

### Core Design Principles
- **Async-first**: All I/O operations are asynchronous
- **Type-safe**: Extensive use of Pydantic models and type hints
- **Configuration-driven**: YAML-based configuration with environment variable support
- **Permission-aware**: Granular control over agent actions (ALLOW/REQUEST/DENY)
- **Context-aware**: Automatic summarization to manage token limits
- **Multi-tenant**: Complete user/session isolation

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Microclaw Service                        │
│  (facets.AsyncioServiceMixin - Service orchestration)       │
└────────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼───┐   ┌───▼────┐   ┌──▼─────────┐
│Channels│   │Agents │   │Cron Tasks │
│(CLI/TG│   │(LLM)   │   │(Scheduled) │
│ etc.)  │   │        │   │           │
└───┬───┘   └──┬─────┘   └──┬─────────┘
    │          │             │
    │    ┌─────▼─────────┐   │
    │    │ Dependency    │   │
    │    │   Resolver    │   │
    │    └─────┬─────────┘   │
    │          │             │
    │    ┌─────┼─────┐       │
    │    │           │       │
┌───▼───▼──┐  ┌────▼────┐  │
│Sessions  │  │Toolkits │  │
│Storage   │  │(MCP/Lang│  │
│(FS/DB)   │  │Chain)   │  │
└──────────┘  └─────────┘  │
                           │
                    ┌──────▼──────┐
                    │ Syncer/Memory│
                    │  (Redis)    │
                    └─────────────┘
```

## Key Features

1. **Multi-User Architecture** - Complete user isolation with user-specific settings, sessions, and agent configurations
2. **Subagent System** - Agent delegation with configurable max_turns and automatic summarization
3. **Automatic Summarization** - Dialogue and memory summarization to manage token limits
4. **Streaming Responses** - Real-time streaming of AI responses
5. **Permission System** - ALLOW/REQUEST/DENY modes for tool operations
6. **Multiple Channels** - CLI, Telegram (polling/webhook), extensible API
7. **Rich Toolkit Ecosystem** - Calendar, Tasks, Email, Filesystem, HomeAssistant, Discogs, etc.
8. **MCP Protocol Support** - Model Context Protocol for external tool integration
9. **Cron Jobs** - System and user-defined scheduled tasks
10. **REST API** - HTTP API for session/user management
