import discogs_client

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.settings import ToolKitSettings
from .dto import (
    DiscogsArtist,
    DiscogsLabel,
    DiscogsMaster,
    DiscogsRelease,
    DiscogsSearchResponse,
    DiscogsSearchResult,
    DiscogsTrack,
)
from .settings import DiscogsToolKitSettings


class DiscogsToolKit(BaseToolKit[DiscogsToolKitSettings]):
    """Tools for interacting with Discogs API."""

    def __init__(self, key: str, settings: ToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._client = discogs_client.Client(
            "Microclaw/1.0",
            user_token=self._settings.personal_token,
        )
        self._client.backoff_enabled = self._settings.retry
        self._client.set_timeout(
            connect=self._settings.timeout,
            read=self._settings.timeout,
        )

    @tool
    async def search(
            self,
            query: str,
            type: str | None = None,
            page: int = 1,
            per_page: int = 50,
    ) -> DiscogsSearchResponse:
        """
        Search for items on Discogs.

        Args:
            query: Search query string
            type: Type of items to search (artist, release, master, label)
            page: Page number for pagination
            per_page: Number of results per page (max 100)

        Returns:
            DiscogsSearchResponse with search results
        """
        results = self._client.search(
            query,
            type=type,
            page=page,
            per_page=per_page,
        )
        return DiscogsSearchResponse(
            results=[
                DiscogsSearchResult(
                    id=r.id,
                    title=r.data.get("title", ""),
                    type=r.data.get("type", ""),
                    resource_url=r.data.get("resource_url", ""),
                    uri=r.data.get("uri", ""),
                    year=r.data.get("year"),
                    artist=r.data.get("artist"),
                    labels=r.data.get("label"),
                    format=r.data.get("format", []),
                    country=r.data.get("country"),
                    genre=r.data.get("genre", []),
                    style=r.data.get("style", []),
                    cover_image=r.data.get("cover_image"),
                )
                for r in results
            ],
            pages=results.pages,
            page=page,
            per_page=results.per_page,
            items=results.count,
        )

    @tool
    async def get_release(self, release_id: int) -> DiscogsRelease:
        """
        Get detailed information about a specific release.

        Args:
            release_id: Discogs release ID

        Returns:
            DiscogsRelease with release details
        """
        release = self._client.release(release_id)
        return self._parse_release(release)

    @tool
    async def get_master(self, master_id: int) -> DiscogsMaster:
        """
        Get detailed information about a master release.

        Args:
            master_id: Discogs master release ID

        Returns:
            DiscogsMaster with master release details
        """
        master = self._client.master(master_id)
        return self._parse_master(master)

    @tool
    async def get_artist(self, artist_id: int) -> DiscogsArtist:
        """
        Get detailed information about an artist.

        Args:
            artist_id: Discogs artist ID

        Returns:
            DiscogsArtist with artist details
        """
        artist = self._client.artist(artist_id)
        return self._parse_artist(artist)

    @tool
    async def get_label(self, label_id: int) -> DiscogsLabel:
        """
        Get detailed information about a label.

        Args:
            label_id: Discogs label ID

        Returns:
            DiscogsLabel with label details
        """
        label = self._client.label(label_id)
        return self._parse_label(label)

    def _parse_artist(self, artist: discogs_client.Artist) -> DiscogsArtist:
        return DiscogsArtist(
            id=artist.id,
            name=artist.name,
            profile=artist.profile,
            url=artist.url,
            images=artist.images,
        )

    def _parse_artist_dict(self, artist_dict: dict) -> DiscogsArtist:
        return DiscogsArtist(
            id=artist_dict.get("id"),
            name=artist_dict.get("name", ""),
            profile=None,
            url=artist_dict.get("resource_url"),
            images=[],
        )

    def _parse_label(self, label: discogs_client.Label) -> DiscogsLabel:
        return DiscogsLabel(
            id=label.id,
            name=label.name,
            profile=label.profile,
            url=label.url,
        )

    def _parse_track(self, track: discogs_client.Track) -> DiscogsTrack:
        return DiscogsTrack(
            position=track.position,
            title=track.title,
            duration=track.duration,
            type_=track.data.get("type_"),
        )

    def _parse_release(self, release: discogs_client.Release) -> DiscogsRelease:
        return DiscogsRelease(
            id=release.id,
            title=release.title,
            artists=[self._parse_artist(a) for a in release.artists],
            labels=[self._parse_label(label) for label in release.labels],
            year=release.year,
            genres=release.genres,
            styles=release.styles,
            tracklist=[self._parse_track(t) for t in release.tracklist],
            country=release.country,
            notes=release.notes,
            url=release.url,
            images=release.images,
        )

    def _parse_master(self, master: discogs_client.Master) -> DiscogsMaster:
        return DiscogsMaster(
            id=master.id,
            title=master.title,
            main_release_id=master.main_release.id if master.main_release else None,
            main_release_url=master.data.get("main_release_url"),
            year=master.year,
            genres=master.genres,
            styles=master.styles,
            artists=[self._parse_artist_dict(a) for a in master.data.get("artists", [])],
            tracklist=[self._parse_track(t) for t in master.tracklist],
            versions_count=len(master.versions) if master.versions else None,
            images=master.images,
            url=master.url,
        )
