from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from microclaw.agents.settings import (
    APITypeEnum,
    ModelCosts,
    ModelSettings,
    ProviderSettings,
)
from microclaw.dto import AgentMessage
from microclaw.stt.settings import STTSettings
from microclaw.stt.stt import STT


@pytest.fixture
def stt_settings() -> STTSettings:
    return STTSettings(language="en")


@pytest.fixture
def stt_model_settings() -> ModelSettings:
    return ModelSettings(
        id="whisper-1",
        costs=ModelCosts(input=0, output=0, currency="$"),
        api_type=APITypeEnum.OPENAI,
    )


@pytest.fixture
def stt_provider_settings() -> ProviderSettings:
    return ProviderSettings(
        base_url="https://api.openai.com/v1",
        api_type=APITypeEnum.OPENAI,
        api_key="test-key",
    )


@pytest.fixture
def mock_stt_client() -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.text = "transcribed text"
    response.usage = None
    client.audio.transcriptions.create = AsyncMock(return_value=response)
    client.close = AsyncMock()
    return client


def _make_stt(stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client):
    with patch.object(STT, "_get_client", return_value=mock_stt_client):
        return STT(
            settings=stt_settings,
            model_settings=stt_model_settings,
            provider_settings=stt_provider_settings,
        )


@pytest.mark.asyncio
async def test_transcribe_success(
    stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client, tmp_path
):
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"fake audio data")

    stt = _make_stt(stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client)

    result = await stt.transcribe(audio_path)

    assert isinstance(result, AgentMessage)
    assert result.role == "stt"
    assert result.text == "transcribed text"
    assert result.spending is not None


@pytest.mark.asyncio
async def test_transcribe_file_not_found(
    stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client
):
    stt = _make_stt(stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client)

    with pytest.raises(FileNotFoundError):
        await stt.transcribe(Path("/nonexistent/file.wav"))


@pytest.mark.asyncio
async def test_transcribe_bytes_success(
    stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client
):
    stt = _make_stt(stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client)

    result = await stt.transcribe_bytes(b"fake audio data", format="wav")

    assert isinstance(result, AgentMessage)
    assert result.role == "stt"
    assert result.text == "transcribed text"


@pytest.mark.asyncio
async def test_transcribe_spending_with_costs(
    stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client, tmp_path
):
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"fake audio data")

    usage = MagicMock()
    usage.type = "duration"
    usage.seconds = 120.5
    mock_stt_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="hi", usage=usage)
    )

    stt = _make_stt(stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client)

    result = await stt.transcribe(audio_path)
    assert result.spending.audio_input_seconds == 120
    assert result.spending.currency == "$"


@pytest.mark.asyncio
async def test_transcribe_spending_without_costs(
    stt_settings, stt_provider_settings, mock_stt_client, tmp_path
):
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"fake audio data")

    model_settings = ModelSettings(
        id="whisper-1",
        costs=None,
        api_type=APITypeEnum.OPENAI,
    )

    stt = _make_stt(stt_settings, model_settings, stt_provider_settings, mock_stt_client)

    result = await stt.transcribe(audio_path)
    assert result.spending.currency == "$"


@pytest.mark.asyncio
async def test_aenter_aexit_closes_client(
    stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client
):
    stt = _make_stt(stt_settings, stt_model_settings, stt_provider_settings, mock_stt_client)

    async with stt:
        pass

    mock_stt_client.close.assert_awaited_once()
