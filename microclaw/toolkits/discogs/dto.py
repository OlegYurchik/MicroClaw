from typing import Any

from pydantic import BaseModel, Field


class DiscogsArtist(BaseModel):
    id: int
    name: str
    profile: str | None = Field(default=None)
    url: str | None = Field(default=None)
    images: list[dict[str, Any]] = Field(default_factory=list)


class DiscogsLabel(BaseModel):
    id: int
    name: str
    profile: str | None = Field(default=None)
    url: str | None = Field(default=None)


class DiscogsTrack(BaseModel):
    position: str | None = Field(default=None)
    title: str
    duration: str | None = Field(default=None)
    type_: str | None = Field(default=None, alias="type")


class DiscogsFormat(BaseModel):
    name: str
    qty: str
    descriptions: list[str] = Field(default_factory=list)


class DiscogsRelease(BaseModel):
    id: int
    title: str
    artists: list[DiscogsArtist] = Field(default_factory=list)
    labels: list[DiscogsLabel] = Field(default_factory=list)
    year: int | None = Field(default=None)
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    formats: list[DiscogsFormat] = Field(default_factory=list)
    tracklist: list[DiscogsTrack] = Field(default_factory=list)
    country: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    url: str | None = Field(default=None)
    images: list[dict[str, Any]] = Field(default_factory=list)


class DiscogsMaster(BaseModel):
    id: int
    title: str
    main_release_id: int | None = Field(default=None)
    main_release_url: str | None = Field(default=None)
    year: int | None = Field(default=None)
    genres: list[str] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    artists: list[DiscogsArtist] = Field(default_factory=list)
    tracklist: list[DiscogsTrack] = Field(default_factory=list)
    versions_count: int | None = Field(default=None)
    images: list[dict[str, Any]] = Field(default_factory=list)
    url: str | None = Field(default=None)


class DiscogsSearchResult(BaseModel):
    id: int
    title: str
    type: str
    resource_url: str
    uri: str
    year: int | None = Field(default=None)
    artist: str | None = Field(default=None)
    labels: list[str] = Field(default_factory=list)
    format: list[str] = Field(default_factory=list)
    country: str | None = Field(default=None)
    genre: list[str] = Field(default_factory=list)
    style: list[str] = Field(default_factory=list)
    cover_image: str | None = Field(default=None)


class DiscogsSearchResponse(BaseModel):
    results: list[DiscogsSearchResult] = Field(default_factory=list)
    pages: int | None = Field(default=None)
    page: int | None = Field(default=None)
    per_page: int | None = Field(default=None)
    items: int | None = Field(default=None)
