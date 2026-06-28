from __future__ import annotations

import enum

from pydantic import AnyHttpUrl, BaseModel, Field, NonNegativeInt, confloat, conint

from microclaw.toolkits import ToolKitSettings


Temperature = confloat(gt=0, le=2)


class APITypeEnum(str, enum.Enum):
    OPENAI = "openai"
    CLOUDRU = "cloudru"
    OLLAMA = "ollama"


class InputTypeEnum(str, enum.Enum):
    TEXT = "text"
    AUDIO = "audio"


class ProviderSettings(BaseModel):
    base_url: AnyHttpUrl
    api_type: APITypeEnum | None = None
    api_key: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class ModelCosts(BaseModel):
    input: float = 0
    output: float = 0
    cache_read: float = 0
    cache_write: float = 0
    audio_input: float = 0
    audio_output: float = 0
    currency: str = "$"

    @property
    def per_tokens(self) -> int:
        return 1_000_000

    @property
    def per_audio_seconds(self) -> int:
        return 1


class ModelSettings(BaseModel):
    id: str
    provider: ProviderSettings | str | None = None
    api_type: APITypeEnum | None = None
    api_key: str | None = None
    costs: ModelCosts | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    temperature: Temperature | None = None
    context_window_size: int | None = Field(default=None, gt=0)
    context_threshold_size: float | None = Field(
        default=0.8,
        gt=0,
        lt=1,
        description=(
            "Threshold for triggering summarization (percentage of max context). None means no "
            "summarization"
        ),
    )
    audio_max_size: int | None = Field(
        default=None,
        gt=0,
        description="Maximum audio file size in bytes. None means no limit",
    )
    input_types: list[InputTypeEnum] = Field(
        default_factory=lambda: [InputTypeEnum.TEXT],
        description="List of supported input types",
    )


class AgentIdentity(BaseModel):
    name: str = "MicroClaw"
    emoji: str = "🤖"
    creature: str = "*(AI? robot? familiar? ghost in the machine? something weirder?)*"
    vibe: str = "*(how do you come across? sharp? warm? chaotic? calm?)*"
    description: str | None = None


class MCPBaseSettings(BaseModel):
    name: str | None = None
    description: str | None = None


class MCPRemoteSettings(MCPBaseSettings):
    url: str


class MCPLocalSettings(MCPBaseSettings):
    command: str
    args: list[str] = Field(default_factory=list)


MCPSettings = MCPRemoteSettings | MCPLocalSettings


class AgentSettings(BaseModel):
    identity: AgentIdentity = AgentIdentity()
    model: ModelSettings | str | None = None
    toolkits: list[ToolKitSettings | str] | None = None
    mcp: list[MCPSettings | str] | None = None
    subagents: list[str | AgentSettings] = Field(default_factory=list)
    temperature: Temperature | None = None
    max_tool_calls: conint(ge=1, le=1000) = 25
    max_model_calls: conint(ge=1, le=1000) = 50
    enable_summarization: bool = True
    enable_memory_flush: bool = True
    max_memory_flush_tokens: conint(ge=50) = 1000
    max_tool_output_chars: conint(ge=100) = 200
    model_max_retries: NonNegativeInt = 3
    model_retry_backoff_factor: confloat(gt=0) = 1.5
    model_retry_initial_delay: confloat(gt=0) = 1
