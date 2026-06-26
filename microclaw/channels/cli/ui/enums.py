import enum


class RoleEnum(str, enum.Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"
