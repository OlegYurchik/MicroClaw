from pydantic import BaseModel, Field


class SessionsToolKitSettings(BaseModel):
    """Settings for the sessions toolkit."""
    
    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of search results to return"
    )
    
    max_messages_per_result: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of matched messages to include per session"
    )
