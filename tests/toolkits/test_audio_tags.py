from unittest.mock import MagicMock

from mutagen.id3 import APIC, ID3
import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.audio_tags.dto import AudioTags
from microclaw.toolkits.audio_tags.toolkit import AudioTagsToolKit
from microclaw.toolkits.enums import PermissionModeEnum


class TestAudioTagsToolKit:
    @pytest.fixture
    def tmp_mp3(self, tmp_path):
        mp3 = tmp_path / "test.mp3"
        id3_header = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 256
        mp3.write_bytes(id3_header + b"\xff\xfb\x90\x00" * 1024)
        return str(mp3)

    @pytest.fixture
    def tmp_mp3_with_cover(self, tmp_path):
        mp3 = tmp_path / "test_cover.mp3"
        id3_header = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 256
        mp3.write_bytes(id3_header + b"\xff\xfb\x90\x00" * 1024)
        audio = ID3(str(mp3))
        audio["APIC:"] = APIC(
            encoding=3,
            mime="image/png",
            type=3,
            desc="",
            data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
        )
        audio.save()
        return str(mp3)

    @pytest.fixture
    def tag_reader(self, tmp_mp3):
        def _reader(path):
            mock = MagicMock()
            mock.filename = path
            mock.mime = ["audio/mpeg"]
            mock.info = MagicMock()
            mock.info.length = 120.0
            mock.info.bitrate = 128000
            mock.info.sample_rate = 44100
            mock.info.channels = 2
            return mock

        return _reader

    @pytest.fixture
    def toolkit(self, tmp_path, tag_reader):
        settings = ToolKitSettings(
            path="microclaw.toolkits.audio_tags.toolkit.AudioTagsToolKit",
            args={"directories": [str(tmp_path)]},
        )
        return AudioTagsToolKit(key="audio", settings=settings, tag_reader=tag_reader)

    @pytest.mark.asyncio
    async def test_read_tags_success(self, toolkit, tmp_mp3):
        info = await toolkit.get_audio_info(tmp_mp3)
        assert info.path == tmp_mp3
        assert info.format == "mpeg"
        assert info.duration == 120.0

    @pytest.mark.asyncio
    async def test_read_tags_file_not_found(self, toolkit, tmp_path):
        with pytest.raises(FileNotFoundError):
            await toolkit.get_audio_info(str(tmp_path / "nonexistent.mp3"))

    @pytest.mark.asyncio
    async def test_read_tags_not_mp3(self, toolkit, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("not mp3")
        with pytest.raises(NotImplementedError):
            await toolkit.get_audio_info(str(txt))

    @pytest.mark.asyncio
    async def test_read_tags_path_outside_allowed(self, toolkit, tmp_path):
        other = tmp_path.parent / "other.mp3"
        other.write_bytes(b"ID3" + b"\x00" * 256 + b"\xff\xfb\x90\x00" * 1024)
        with pytest.raises(PermissionError):
            await toolkit.get_audio_info(str(other))

    @pytest.mark.asyncio
    async def test_write_tags_success(self, toolkit, tmp_mp3, tmp_path):
        toolkit._arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.set_tags(
            tmp_mp3, {"title": "Test Title", "artist": "Test Artist"}
        )

    @pytest.mark.asyncio
    async def test_write_tags_denied(self, toolkit, tmp_mp3):
        toolkit._arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.set_tags(tmp_mp3, {"title": "Test"})

    @pytest.mark.asyncio
    async def test_write_tags_invalid_key_skipped(self, toolkit, tmp_mp3):
        toolkit._arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.set_tags(tmp_mp3, {"unknown_key": "value", "title": None})

    @pytest.mark.asyncio
    async def test_write_tags_request_mode(self, toolkit, tmp_mp3):
        toolkit._arguments.write_mode = PermissionModeEnum.REQUEST
        with pytest.raises(Exception):
            await toolkit.set_tags(tmp_mp3, {"title": "Test"})

    @pytest.mark.asyncio
    async def test_get_tags_success(self, toolkit, tmp_mp3):
        tags = await toolkit.get_tags(tmp_mp3)
        assert isinstance(tags, AudioTags)

    @pytest.mark.asyncio
    async def test_get_cover_no_cover(self, toolkit, tmp_mp3):
        cover = await toolkit.get_cover(tmp_mp3)
        assert cover is None

    @pytest.mark.asyncio
    async def test_get_cover_with_cover(self, toolkit, tmp_mp3_with_cover):
        cover = await toolkit.get_cover(tmp_mp3_with_cover)
        assert cover is not None
        assert cover.mime_type == "image/png"

    @pytest.mark.asyncio
    async def test_set_cover_success(self, toolkit, tmp_mp3):
        toolkit._arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.set_cover(
            tmp_mp3,
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        )

    @pytest.mark.asyncio
    async def test_set_cover_denied(self, toolkit, tmp_mp3):
        toolkit._arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.set_cover(
                tmp_mp3,
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            )

    @pytest.mark.asyncio
    async def test_set_cover_request_mode(self, toolkit, tmp_mp3):
        toolkit._arguments.write_mode = PermissionModeEnum.REQUEST
        with pytest.raises(Exception):
            await toolkit.set_cover(
                tmp_mp3,
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            )

    @pytest.mark.asyncio
    async def test_remove_cover_success(self, toolkit, tmp_mp3_with_cover):
        toolkit._arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.remove_cover(tmp_mp3_with_cover)

    @pytest.mark.asyncio
    async def test_remove_cover_no_cover(self, toolkit, tmp_mp3):
        toolkit._arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.remove_cover(tmp_mp3)

    @pytest.mark.asyncio
    async def test_remove_cover_denied(self, toolkit, tmp_mp3_with_cover):
        toolkit._arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.remove_cover(tmp_mp3_with_cover)

    @pytest.mark.asyncio
    async def test_remove_cover_request_mode(self, toolkit, tmp_mp3_with_cover):
        toolkit._arguments.write_mode = PermissionModeEnum.REQUEST
        with pytest.raises(Exception):
            await toolkit.remove_cover(tmp_mp3_with_cover)
