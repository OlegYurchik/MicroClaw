import enum


class PermissionModeEnum(str, enum.Enum):
    ALLOW = "allow"
    REQUEST = "request"
    DENY = "deny"


class SourceModeEnum(str, enum.Enum):
    ALL = "all"
    GLOBAL = "global"
    MARKETPLACE = "marketplace"
    EMPTY = "empty"
