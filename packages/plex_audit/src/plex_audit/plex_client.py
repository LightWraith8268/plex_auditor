from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from plexapi.server import PlexServer

from plex_audit.config import PlexConfig


@dataclass(frozen=True)
class Library:
    title: str
    kind: str  # "movie" | "show"
    raw: Any


@dataclass(frozen=True)
class MediaFile:
    plex_path: str
    rating_key: str


class PlexClient:
    def __init__(self, config: PlexConfig) -> None:
        self._config = config
        self._server: PlexServer | None = None
        self._libraries_cache: list[Library] | None = None

    @property
    def server(self) -> PlexServer:
        if self._server is None:
            self._server = PlexServer(  # type: ignore[no-untyped-call]
                self._config.url,
                self._config.token,
                timeout=self._config.timeout_seconds,
            )
        return self._server

    def iter_libraries(self) -> Iterator[Library]:
        if self._libraries_cache is None:
            sections = self.server.library.sections()
            self._libraries_cache = [
                Library(title=section.title, kind=section.type, raw=section)
                for section in sections
            ]
        yield from self._libraries_cache

    def get_media_files(self, item: Any) -> Iterator[MediaFile]:
        rating_key = str(getattr(item, "ratingKey", ""))
        for media in getattr(item, "media", []) or []:
            for part in getattr(media, "parts", []) or []:
                path = getattr(part, "file", None)
                if path:
                    yield MediaFile(plex_path=path, rating_key=rating_key)
