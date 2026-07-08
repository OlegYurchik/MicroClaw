from microclaw.dto import DecisionEnum
from langgraph.types import interrupt
import base64
import pathlib
from typing import Any

from mutagen import File
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.execptions import UserDeniedAction
from .dto import AudioFileInfo, AudioTags, CoverImage
from .settings import AudioTagsToolKitSettings


class AudioTagsToolKit(BaseToolKit[AudioTagsToolKitSettings]):
    """Tools for managing audio file tags and metadata."""

    def __init__(self, key: str, settings: AudioTagsToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._allowed_paths = [
            pathlib.Path(directory).resolve()
            for directory in self._settings.directories
        ]

    @tool
    async def get_audio_info(self, path: str) -> AudioFileInfo:
        """
        Get detailed information about an audio file including tags.

        Args:
            path: Path to the audio file

        Returns:
            AudioFileInfo object with file information and tags
        """
        audio = self._get_audio_file(path)
        tags = self._extract_tags(audio)
        stat = pathlib.Path(path).stat()

        return AudioFileInfo(
            path=path,
            format=audio.mime[0].split("/")[-1] if audio.mime else "unknown",
            duration=tags.length or 0,
            bitrate=tags.bitrate,
            sample_rate=tags.sample_rate,
            channels=tags.channels,
            size=stat.st_size,
            tags=tags,
        )

    @tool
    async def get_tags(self, path: str) -> AudioTags:
        """
        Get tags from an audio file.

        Args:
            path: Path to the audio file

        Returns:
            AudioTags object with all tags
        """
        audio = self._get_audio_file(path)
        return self._extract_tags(audio)

    @tool
    async def get_cover(self, path: str) -> CoverImage | None:
        """
        Get cover image from an audio file.

        Args:
            path: Path to the audio file

        Returns:
            CoverImage object with cover data or None if no cover exists
        """
        self._get_audio_file(path)

        id3 = ID3(path)
        if "APIC:" not in id3:
            return None

        apic = id3["APIC:"]
        return CoverImage(
            mime_type=apic.mime,
            data=base64.b64encode(apic.data).decode("utf-8"),
        )

    @tool
    async def set_tags(self, path: str, tags: dict[str, Any]) -> None:
        """
        Set tags for an audio file.

        Args:
            path: Path to the audio file
            tags: Dictionary of tags to set (title, artist, album, etc.)

        Returns:
            None - indicates successful operation
        """

        self._get_audio_file(path)
        if self._settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write data to files denied")

        audio = EasyID3(path)

        tag_map = {
            "title": "title",
            "artist": "artist",
            "album": "album",
            "albumartist": "albumartist",
            "year": "date",
            "date": "date",
            "genre": "genre",
            "comment": "comment",
            "composer": "composer",
            "performer": "performer",
            "copyright": "copyright",
            "encoded_by": "encoded-by",
            "url": "url",
            "isrc": "isrc",
            "bpm": "bpm",
            "initial_key": "initialkey",
            "track": "tracknumber",
            "total_tracks": "tracktotal",
            "disc": "discnumber",
            "total_discs": "disctotal",
        }

        for key, value in tags.items():
            if key not in tag_map or value is None:
                continue

            target_key = tag_map[key]
            if target_key in audio:
                del audio[target_key]
            audio[target_key] = str(value)

        if self._settings.write_mode is PermissionModeEnum.REQUEST:
            tags_text = "\n".join(f"{tag} = {value}" for tag, value in tags.items())
            confirmation_request_text = f"Write tags to {path}?\n\n{tags_text}\n"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT:
                raise UserDeniedAction()

        audio.save()

    @tool
    async def set_cover(
        self, path: str, image_data: str, mime_type: str = "image/jpeg"
    ) -> None:
        """
        Set cover image for an audio file.

        Args:
            path: Path to the audio file
            image_data: Base64 encoded image data
            mime_type: MIME type of the image (default: image/jpeg)

        Returns:
            None - indicates successful operation
        """
        self._get_audio_file(path)
        if self._settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write data to files denied")

        cover_bytes = base64.b64decode(image_data)

        id3 = ID3(path)
        id3["APIC:"] = APIC(
            encoding=3,
            mime=mime_type,
            type=3,
            desc="",
            data=cover_bytes,
        )

        if self._settings.write_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Set cover to audio '{path}'?"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        id3.save()

    @tool
    async def remove_cover(self, path: str) -> None:
        """
        Remove cover image from an audio file.

        Args:
            path: Path to the audio file

        Returns:
            None - indicates successful operation
        """
        self._get_audio_file(path)
        if self._settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write data to files denied")

        id3 = ID3(path)
        if "APIC:" not in id3:
            return

        if self._settings.allow_write is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Remove cover from audio '{path}'?"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        del id3["APIC:"]
        id3.save()

    def _get_audio_file(self, path_str: str) -> File:
        path = pathlib.Path(path_str).resolve()

        for allowed_path in self._allowed_paths:
            try:
                path.relative_to(allowed_path)
                break
            except ValueError:
                continue
        else:
            raise PermissionError(
                f"Path '{path_str}' is not within allowed directories: {self._settings.directories}"
            )

        if not path.exists():
            raise FileNotFoundError(f"File '{path}' does not exist")
        if not path.is_file():
            raise ValueError(f"Path '{path}' is not a file")
        if path.suffix.lower() != ".mp3":
            raise NotImplementedError("Only MP3 files are currently supported")
        return File(path)

    def _extract_tags(self, audio: File) -> AudioTags:
        tags = AudioTags()

        tag_mapping = {
            "title": lambda v: setattr(tags, "title", str(v)),
            "artist": lambda v: setattr(tags, "artist", str(v)),
            "album": lambda v: setattr(tags, "album", str(v)),
            "albumartist": lambda v: setattr(tags, "albumartist", str(v)),
            "genre": lambda v: setattr(tags, "genre", str(v)),
            "comment": lambda v: setattr(tags, "comment", str(v)),
            "composer": lambda v: setattr(tags, "composer", str(v)),
            "performer": lambda v: setattr(tags, "performer", str(v)),
            "copyright": lambda v: setattr(tags, "copyright", str(v)),
            "encoded-by": lambda v: setattr(tags, "encoded_by", str(v)),
            "url": lambda v: setattr(tags, "url", str(v)),
            "isrc": lambda v: setattr(tags, "isrc", str(v)),
            "initialkey": lambda v: setattr(tags, "initial_key", str(v)),
        }

        int_tag_mapping = {
            "date": lambda v: setattr(tags, "year", int(str(v)[:4])),
            "tracknumber": lambda v: setattr(tags, "track", int(str(v))),
            "tracktotal": lambda v: setattr(tags, "total_tracks", int(str(v))),
            "discnumber": lambda v: setattr(tags, "disc", int(str(v))),
            "disctotal": lambda v: setattr(tags, "total_discs", int(str(v))),
            "bpm": lambda v: setattr(tags, "bpm", int(str(v))),
        }

        easy_tags = EasyID3(audio.filename)
        for key, value in easy_tags.items():
            if isinstance(value, list) and value:
                value = value[0]

            key_lower = key.lower()

            if key_lower in tag_mapping:
                tag_mapping[key_lower](value)
            elif key_lower in int_tag_mapping:
                try:
                    int_tag_mapping[key_lower](value)
                except (ValueError, IndexError):
                    pass
            else:
                tags.custom_tags[key] = str(value)

        tags.length = audio.info.length if audio.info else None
        tags.bitrate = (
            int(audio.info.bitrate / 1000)
            if audio.info and audio.info.bitrate
            else None
        )
        tags.sample_rate = audio.info.sample_rate if audio.info else None
        tags.channels = audio.info.channels if audio.info else None

        id3 = ID3(audio.filename)
        if "APIC:" in id3:
            tags.has_cover = True
            apic = id3["APIC:"]
            tags.cover_mime_type = apic.mime
            tags.cover_data = base64.b64encode(apic.data).decode("utf-8")

        return tags
