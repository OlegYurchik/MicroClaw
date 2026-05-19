# MicroClaw 🤖

> A distributed AI agent framework with synchronized instances across multiple platforms

MicroClaw is a scalable framework for building personal AI assistants that can seamlessly manage your calendars, tasks, files, contacts, and home automation from multiple interfaces with full synchronization across all instances.

## Why MicroClaw?

- **🧠 Distributed Architecture** - Multiple synchronized instances across different platforms
- **🎛️ Full Control** - Complete control over agent behavior via YAML configuration
- **🔌 Modular Toolkits** - Extensible toolkit system with permission management
- **🔒 Permission Control** - AI asks for permission before executing sensitive toolkit operations
- **⚙️ Multi-Provider Support** - OpenAI, Cloud.ru, Ollama and more
- **💬 Multi-Platform** - Telegram, CLI - interact anywhere with full sync

## Key Features

### Distributed & Synchronized

Multiple MicroClaw instances running on different platforms automatically synchronize sessions, context, and state. Whether you're chatting via Telegram or using CLI, your conversation maintains continuity across all platforms.

### Modular Toolkits System

The core innovation of MicroClaw is its toolkit system:

- **Modular Design** - Each toolkit provides specific functionality (calendar, tasks, email, home automation, etc.)
- **Permission Handling** - AI asks for user permission before executing sensitive toolkit operations
- **Easy Extension** - Create custom toolkits with minimal code
- **Smart Tool Selection** - AI automatically selects appropriate toolkits based on task context

### Permission-Based Execution

Before performing sensitive operations in toolkits, the AI:
1. Explains what action it will perform
2. Requests your permission
3. Executes only after confirmation
4. Provides feedback on results

This ensures you remain in control while the AI handles complex workflows.

### Extensive Integrations

Support for various services through modular Toolkits:

- **📅 CalDAV** - Google Calendar, Outlook, Nextcloud calendars
- **✅ Tasks** - Google Tasks, Nextcloud Tasks
- **📚 CardDAV** - Contacts from Google, Nextcloud
- **📂 WebDAV** - Nextcloud and other WebDAV file storage
- **📧 Email** - IMAP/SMTP for Gmail, Outlook, Yahoo and others
- **🏠 Home Assistant** - Smart home control and automation
- **💿 Discogs** - Music release database integration
- **🌐 MCP** - Model Context Protocol for extended capabilities

### Subagent System

Hierarchical agent management with specialized subagents:

```yaml
agents:
  personal_assistant:
    model: qwen3_coder_next
    identity:
      name: "MicroClaw"
      emoji: "🤖"
      creature: "AI"
      vibe: "helpful"
    subagents:
      - butler
      - travel_agent

  butler:
    identity:
      name: "Kuzya"
      emoji: "🤵🏻"
      creature: "robot"
      vibe: "mannerly"
    toolkits:
      - homeassistant
```

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/microclaw.git
cd microclaw

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install default dependencies
pip install -e ".telegram,openai"
# Add other dependencies as needed:
# database, tasks, caldav, carddav, webdav, email, homeassistant, discogs
```

### Configuration

Copy the example configuration file:

```bash
cp config.example.yaml config.yaml
```

Create a `.env` file with your secrets:

```bash
cp .env.example .env
```

Configure providers, agents, and toolkits in `config.yaml`.

### Running

```bash
# Start Telegram bot
python -m microclaw channels telegram

# Start CLI channel
python -m microclaw channels cli
```

All instances will automatically synchronize sessions and context.

## Configuration

MicroClaw is fully controlled via YAML configuration:

```yaml
providers:
  cloud_ru:
    base_url: https://foundation-models.api.cloud.ru/v1
    api_type: openai
    api_key: your_api_key

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
      - personal_tasks
      - personal_files
    mcp:
      - websearch

toolkits:
  personal_calendar:
    path: microclaw.toolkits.caldav.CalDAVToolKit
    args:
      url: https://your-nextcloud.com/remote.php/dav
      username: your_username
      password: your_password

channels:
  telegram:
    agent: personal_assistant
    sessions_storage: default
    users_storage: default
    type: telegram
    method: polling
    name: Your Assistant Bot
    token: your_bot_token
    allow_from: [username]
```

## Architecture

- **Agents** - AI entities with unique identity and access to toolkits
- **Subagents** - Specialized agents delegated by main agents
- **Channels** - Communication interfaces (Telegram, CLI)
- **Toolkits** - Modular integrations with external services
- **Permission System** - User confirmation for sensitive operations
- **MCP** - Model Context Protocol for extending agent capabilities
- **Storages** - Persistent storage for sessions and users
- **Synchronization** - Multi-instance session and context sync
- **Cron** - Scheduled task automation

## Usage

### Basic Commands

```bash
# View available commands
python -m microclaw --help

# Channel information
python -m microclaw channels --help

# Run specific agent
python -m microclaw run --agent personal_assistant
```

### Example Scenarios

**Calendar & Tasks Management**:
```
User: Schedule a meeting with the team tomorrow at 14:00
MicroClaw: I'll create a calendar event: "Team Meeting" tomorrow at 14:00-15:00
User: OK
MicroClaw: ✅ Meeting created successfully
```

**Email Processing**:
```
User: Mark all marketing emails from this week as read
MicroClaw: I'll mark 12 marketing emails as read. Is that OK?
User: Yes
MicroClaw: ✅ Processed 12 emails
```

**File Operations**:
```
User: Copy the latest project files to my backup folder
MicroClaw: I'll copy 15 files from ./projects to ./backup. Proceed?
User: Confirm
MicroClaw: ✅ Backup completed successfully
```

**Smart Home Control**:
```
User: Turn off all devices when I leave home
MicroClaw: I'll turn off 8 devices: lights, TV, AC, etc. OK?
User: Yes
MicroClaw: ✅ All devices turned off
```

## Toolkit Development

### Creating Custom Toolkits

```python
from microclaw.toolkits import BaseToolKit, tool

class CustomToolKit(BaseToolKit):
    @tool
    def custom_action(self, param: str) -> str:
        return f"Processed: {param}"
    
    @tool
    def sensitive_operation(self, data: str) -> str:
        return f"Modified: {data}"
```

Available toolkits:
- `microclaw.toolkits.caldav` - Calendar management
- `microclaw.toolkits.tasks` - Task management
- `microclaw.toolkits.carddav` - Contact management
- `microclaw.toolkits.webdav` - File operations
- `microclaw.toolkits.email` - Email processing
- `microclaw.toolkits.homeassistant` - Smart home control
- `microclaw.toolkits.discogs` - Music database

## AI Provider Options

- **OpenAI** - Standard GPT-4/GPT-3.5
- **Cloud.ru** - Regional provider
- **Ollama** - Self-hosted models
- Any OpenAI-compatible API

## Architecture Overview

See the project's internal documentation for technical details:
- Configuration files in `.ai/` directory
- Source code in `microclaw/` directory
- Toolkits in `microclaw/toolkits/`
- Channels in `microclaw/channels/`

## Contributing

We welcome contributions!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is GPLv3-licensed. See the [LICENSE](LICENSE) file for details.

## Contact

- **Issues**: https://github.com/your-username/microclaw/issues
- **Discussions**: https://github.com/your-username/microclaw/discussions

---

**MicroClaw** - Synchronized AI agents that work together across all your platforms, powered by modular toolkits and permission-safe execution.

⚠️ **Note**: Always use environment variables for API keys and never commit them to the repository.
