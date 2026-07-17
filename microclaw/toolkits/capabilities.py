import enum


class ToolKitCapability(str, enum.Enum):
    CURRENT_USER = "current_user"
    ALL_USERS = "all_users"
    CURRENT_SESSION = "current_session"
    ALL_SESSIONS = "all_sessions"


class DiscoveryCapability(str, enum.Enum):
    MODELS = "models"
    TOOLKITS = "toolkits"
    SKILLS = "skills"
    AGENTS = "agents"
    MCP = "mcp"
