import contextvars
import uuid
from dataclasses import dataclass

from microclaw.toolkits.accessors import (
    AllSessionsAccessor,
    AllUsersAccessor,
    CurrentSessionAccessor,
    CurrentUserAccessor,
    UserSessionsAccessor,
)
from microclaw.toolkits.dto import DiscoveryInfo


@dataclass(frozen=True)
class ToolkitExecutionContext:
    session_id: uuid.UUID
    request_id: uuid.UUID
    channel_key: str
    channel_internal_id: str

    # User / session accessors (controlled by ToolKitCapability)
    current_user_accessor: CurrentUserAccessor | None = None
    all_users_accessor: AllUsersAccessor | None = None
    user_sessions_accessor: UserSessionsAccessor | None = None
    current_session_accessor: CurrentSessionAccessor | None = None
    sessions_accessor: AllSessionsAccessor | None = None

    # Discovery (controlled by DiscoveryCapability)
    all_models: dict[str, DiscoveryInfo] | None = None
    all_toolkits: dict[str, DiscoveryInfo] | None = None
    all_skills: dict[str, DiscoveryInfo] | None = None
    all_agents: dict[str, DiscoveryInfo] | None = None
    all_mcp: dict[str, DiscoveryInfo] | None = None


TOOLKIT_CONTEXT = contextvars.ContextVar("toolkit_context", default=None)


def get_toolkit_context() -> ToolkitExecutionContext | None:
    return TOOLKIT_CONTEXT.get(None)
