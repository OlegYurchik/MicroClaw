import enum


class PermissionModeEnum(str, enum.Enum):
    ALLOW = "allow"
    REQUEST = "request"
    DENY = "deny"
