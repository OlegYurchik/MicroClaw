from pydantic import BaseModel, Field


class TelegramToolKitSettings(BaseModel):
    bot_token: str = Field(description="Telegram bot token")
