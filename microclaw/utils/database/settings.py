from pydantic import AnyUrl, BaseModel, PositiveInt


class DatabaseSettings(BaseModel):
    dsn: AnyUrl = "sqlite+aiosqlite:///db.sqlite3"
    pool_size: PositiveInt = 5
    pool_recycle: PositiveInt = 60  # in seconds: 1 minute
    pool_timeout: PositiveInt = 60  # in seconds: 1 minute
