import pathlib
from io import BytesIO
from typing import Self

from openai import AsyncOpenAI

from microclaw.agents.settings import ModelSettings, ProviderSettings, APITypeEnum
from microclaw.dto import AgentMessage, Spending
from microclaw.stt.settings import STTSettings


class STT:
    def __init__(
            self,
            settings: STTSettings,
            model_settings: ModelSettings,
            provider_settings: ProviderSettings,
    ) -> None:
        self._settings = settings
        self._model_settings = model_settings
        self._provider_settings = provider_settings
        self._client = self._get_client()

    def _get_client(self) -> AsyncOpenAI:
        api_type = self._model_settings.api_type or self._provider_settings.api_type
        api_key = self._model_settings.api_key or self._provider_settings.api_key
        if not api_key:
            raise ValueError("API key for STT not provided")
        base_url = str(self._provider_settings.base_url)

        match api_type:
            case APITypeEnum.OPENAI:
                return AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url if base_url != "https://api.openai.com/v1" else None,
                )
            case _:
                raise ValueError(f"Unsupported API type: '{api_type.value}'")

    async def transcribe(self, audio_path: pathlib.Path | str) -> AgentMessage:
        path = pathlib.Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with path.open("rb") as audio_file:
            response = await self._client.audio.transcriptions.create(
                model=self._model_settings.id,
                file=audio_file,
                language=self._settings.language,
            )

        spending = Spending(
            audio_input_seconds=int(response.duration) if hasattr(response, "duration") else 0,
            currency=self._model_settings.costs.currency if self._model_settings.costs else "$",
        )
        if self._model_settings.costs:
            spending.calculate_cost(model_costs=self._model_settings.costs)

        return AgentMessage(
            role="stt",
            text=response.text,
            spending=spending,
        )

    async def transcribe_bytes(self, audio_data: bytes, format: str = "wav") -> AgentMessage:
        audio_file = BytesIO(audio_data)
        audio_file.name = f"audio.{format}"

        response = await self._client.audio.transcriptions.create(
            model=self._model_settings.id,
            file=audio_file,
            language=self._settings.language,
        )

        spending = Spending(
            audio_input_seconds=int(response.duration) if hasattr(response, "duration") else 0,
            currency=self._model_settings.costs.currency if self._model_settings.costs else "$",
        )
        if self._model_settings.costs:
            spending.calculate_cost(model_costs=self._model_settings.costs)

        return AgentMessage(
            role="stt",
            text=response.text,
            spending=spending,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.close()
