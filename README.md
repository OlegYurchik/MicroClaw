# 🦞 Microclaw — Personal AI Assistant

<p align="center">
    <strong>Secure. Pythonic. Yours.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge" alt="Python 3.11+"></a>
</p>

**Microclaw** is a _personal AI assistant_ you run on your own devices.

Unlike OpenClaw, Moltis, Nanobot and others, Microclaw does **not** have full access to the system it runs on. It uses only **explicitly defined tools**. The model has **no access to authorization data** for tool operations.

**Key difference:** Microclaw is written in Python by a real developer (not AI), making the code readable and concise. Python was chosen for clarity and understandability of the platform.

**Unique feature:** The **toolkit system** — a set of logically grouped tools. This approach allows the model to more accurately determine which tool to call, avoiding unnecessary tool and model invocations.

**Philosophy:** Like Python, Microclaw is a platform with "batteries included" — but you need to insert the batteries yourself. The platform provides the foundation, but you configure and enable the tools you need.

**Code quality:** Many projects compare themselves by LoC (Lines of Code), claiming less is better. In Microclaw, the primary metric is **architecture and code clarity**, not quantity. The code is written to be understood and maintained.

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/OlegYurchik/microclaw.git
cd microclaw

# Install dependencies and run
uv run microclaw run
```

### Using Docker Compose

```bash
# Clone the repository
git clone https://github.com/OlegYurchik/microclaw.git
cd microclaw

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys

# Run with Docker Compose
docker-compose up -d
```

## Quick Start

```bash
# Run the service
uv run microclaw run

# Run an agent in CLI mode
uv run microclaw agents run

# Run with additional options
uv run microclaw agents run --loader --costs --context-usage --debug
```

## Architecture

Microclaw follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                        Channels                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │   CLI    │  │ Telegram │  │   ...    │  │   ...    │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │       Agent Core          │
        │  (Tool Selection &        │
        │   Execution)              │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │      Toolkits             │
        │  ┌─────────────────────┐  │
        │  │ CalDAV  │ CardDAV   │  │
        │  │ Email   │ WebDAV    │  │
        │  │   ...      ...      │  │
        │  └─────────────────────┘  │
        └─────────────┬─────────────┘
                      │
        ┌─────────────▼─────────────┐
        │   Session Storage         │
        │  (Memory | Filesystem)    │
        └───────────────────────────┘
```

## Features

### 🔒 Security by Design

- **No system access** — The model can only use explicitly defined tools
- **Credential isolation** — Authorization data is never exposed to the model
- **Explicit tool permissions** — Each tool must be explicitly enabled

### 🧩 Toolkit System

Toolkits are logical groups of related tools. Each toolkit is configured independently and can be enabled/disabled per agent.

| Toolkit | Description |
|---------|-------------|
| **CalDAV** | Calendar operations (events, tasks) |
| **CardDAV** | Contact management |
| **Email** | Email operations (IMAP/SMTP) |
| **WebDAV** | File operations on WebDAV servers |

### 📦 Modular Architecture

- **Channels** — Pluggable communication interfaces (CLI, Telegram, ...)
- **Session Storage** — Multiple backends (in-memory, filesystem)
- **Toolkits** — Extensible tool system with clear interfaces

### 🐍 Pythonic Codebase

- Written by a real developer, not AI-generated
- Clean, readable, and maintainable code
- Type hints throughout
- Clear architecture over minimal LoC

## Configuration

Create a `config.yaml` file:

```yaml
providers:
  default:
    base_url: https://api.openai.com/v1
    api_type: openai
    api_key: !env OPENAI_API_KEY

models:
  default:
    id: gpt-4o

agents:
  default:
    identity:
      name: MicroClaw
      emoji: "🤖"
    model: default
    toolkits:
      - email
    temperature: 0.7
    max_tool_calls: 25
    enable_summarization: true

channels:
  default:
    type: telegram
    token: !env TELEGRAM_BOT_TOKEN
    method: polling
    allow_from:
      - 123456789

sessions_storages:
  default:
    type: filesystem

toolkits:
  - name: email
    path: microclaw.toolkits.email.EmailToolKit
    args:
      smtp_host: smtp.gmail.com
      smtp_port: 465
      smtp_tls_mode: ssl
      imap_host: imap.gmail.com
      imap_port: 993
      imap_tls_mode: ssl
      username: !env EMAIL_USERNAME
      password: !env EMAIL_PASSWORD
```

### Environment Variables

Create a `.env` file:

```bash
OPENAI_API_KEY=your_openai_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
```

## Channels

### CLI Channel

The default channel for local interaction:

```bash
# Run agent in CLI mode
uv run microclaw agents run

# With additional options
uv run microclaw agents run --loader --costs --context-usage --debug
```

Options:
- `--loader` — Show loading indicator
- `--costs` — Show token costs
- `--context-usage` — Show context usage
- `--debug` — Enable debug output

### Telegram Channel

Supports both polling and webhook modes:

```yaml
channels:
  default:
    type: telegram
    token: !env TELEGRAM_BOT_TOKEN
    method: polling  # or "webhook"
    allow_from:
      - 123456789  # User IDs allowed to interact
```

## Session Storage

### Memory Storage

Fast, in-memory storage (non-persistent):

```yaml
sessions_storages:
  default:
    type: memory
```

### Filesystem Storage

Persistent storage using JSON files:

```yaml
sessions_storages:
  default:
    type: filesystem
```

## Development

```bash
# Clone the repository
git clone https://github.com/OlegYurchik/microclaw.git
cd microclaw

# Install dependencies (including toolkits)
uv sync --all-groups

# Run the service
uv run microclaw run
```

## Project Structure

```
microclaw/
├── agents/           # Agent core and logic
│   ├── agent.py      # Main agent implementation
│   ├── cli.py        # CLI commands for agents
│   └── settings.py   # Agent configuration
├── channels/         # Communication channels
│   ├── cli/         # CLI channel
│   └── telegram/    # Telegram channel (polling + webhook)
├── sessions_storages/ # Session persistence backends
│   ├── memory/      # In-memory storage
│   └── filesystem/  # File-based storage
├── toolkits/        # Tool implementations
│   ├── base.py      # Base toolkit class
│   ├── caldav/      # Calendar toolkit
│   ├── carddav/     # Contacts toolkit
│   ├── email/       # Email toolkit
│   └── webdav/      # WebDAV toolkit
├── cli.py           # Main CLI entry point
├── settings.py      # Global settings
└── service.py       # Main service
```

## Comparison

| Feature | OpenClaw | Moltis | **Microclaw** |
|---------|----------|--------|--------------|
| Language | TypeScript | Rust | **Python** |
| System Access | Full | Sandboxed | **Explicit tools only** |
| Credential Exposure | Possible | Isolated | **Never exposed to model** |
| Code Origin | AI-generated | Human-written | **Human-written** |
| Toolkit System | No | No | **Yes** |
| Runtime | Node.js | Single binary | **Python 3.11+ (uv)** |
| Session Storage | Multiple | SQLite | **Memory + Filesystem** |
| Primary Metric | Features | Performance | **Code clarity** |
| Installation | npm | Binary | **uv / Docker** |

## TODO

- [ ] Cron tasks service
- [ ] Toolkit for cron tasks service
- [ ] STT
- [ ] Multiple users system — optional

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

Inspired by [OpenClaw](https://github.com/openclaw/openclaw), [Moltis](https://github.com/moltis-org/moltis), [NanoClaw](https://github.com/qwibitai/nanoclaw), [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) and [SafeClaw](https://github.com/princezuda/safeclaw).
