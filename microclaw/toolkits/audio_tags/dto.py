from typing import Any

from pydantic import BaseModel, Field


class AudioTags(BaseModel):
    title: str | None = Field(default=None)
    artist: str | None = Field(default=None)
    album: str | None = Field(default=None)
    albumartist: str | None = Field(default=None)
    year: int | None = Field(default=None)
    track: int | None = Field(default=None)
    total_tracks: int | None = Field(default=None)
    disc: int | None = Field(default=None)
    total_discs: int | None = Field(default=None)
    genre: str | None = Field(default=None)
    comment: str | None = Field(default=None)
    composer: str | None = Field(default=None)
    performer: str | None = Field(default=None)
    copyright: str | None = Field(default=None)
    encoded_by: str | None = Field(default=None)
    url: str | None = Field(default=None)
    isrc: str | None = Field(default=None)
    bpm: int | None = Field(default=None)
    initial_key: str | None = Field(default=None)
    length: float | None = Field(default=None)
    bitrate: int | None = Field(default=None)
    sample_rate: int | None = Field(default=None)
    channels: int | None = Field(default=None)
    has_cover: bool = Field(default=False)
    cover_mime_type: str | None = Field(default=None)
    cover_data: str | None = Field(default=None)
    custom_tags: dict[str, Any] = Field(default_factory=dict)


class AudioFileInfo(BaseModel):
    path: str
    format: str
    duration: float
    bitrate: int | None = Field(default=None)
    sample_rate: int | None = Field(default=None)
    channels: int | None = Field(default=None)
    size: int
    tags: AudioTags


class CoverImage(BaseModel):
    mime_type: str
    width: int | None = Field(default=None)
    height: int | None = Field(default=None)
    data: str
