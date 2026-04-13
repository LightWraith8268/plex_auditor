from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

from plex_audit.context import FindingsSink, ScanContext
from plex_audit.path_mapper import PathMapper, PathMapping
from plex_audit.plex_client import Library, MediaFile


@dataclass
class FakeEpisode:
    index: int
    files: list[str]
    season_index: int = 1
    show_title: str = ""
    rating_key: str = ""


@dataclass
class FakeSeason:
    index: int
    episodes: list[FakeEpisode] = field(default_factory=list)


@dataclass
class FakeShowBuilder:
    title: str
    year: int | None = None
    seasons: list[FakeSeason] = field(default_factory=list)

    def add_season(self, number: int, episodes: list[tuple[int, list[str]]]) -> FakeSeason:
        season = FakeSeason(index=number, episodes=[])
        for ep_index, files in episodes:
            season.episodes.append(
                FakeEpisode(index=ep_index, files=files, season_index=number, show_title=self.title)
            )
        self.seasons.append(season)
        return season


@dataclass
class FakeMovie:
    title: str
    year: int | None
    files: list[str]
    has_poster: bool = True
    has_summary: bool = True
    is_matched: bool = True
    rating_key: str = ""
    collections: list[str] = field(default_factory=list)


class PlexFake:
    def __init__(self) -> None:
        self._movies: list[FakeMovie] = []
        self._shows: list[FakeShowBuilder] = []
        self._next_rating_key = 1000

    def _new_key(self) -> str:
        self._next_rating_key += 1
        return str(self._next_rating_key)

    def add_movie(
        self,
        title: str,
        year: int | None = None,
        files: list[str] | None = None,
        has_poster: bool = True,
        has_summary: bool = True,
        is_matched: bool = True,
        collections: list[str] | None = None,
    ) -> FakeMovie:
        movie = FakeMovie(
            title=title,
            year=year,
            files=files or [],
            has_poster=has_poster,
            has_summary=has_summary,
            is_matched=is_matched,
            rating_key=self._new_key(),
            collections=collections or [],
        )
        self._movies.append(movie)
        return movie

    def add_show(self, title: str, year: int | None = None) -> FakeShowBuilder:
        show = FakeShowBuilder(title=title, year=year)
        self._shows.append(show)
        return show

    def _movie_mock(self, movie: FakeMovie) -> MagicMock:
        item = MagicMock()
        item.title = movie.title
        item.year = movie.year
        item.ratingKey = movie.rating_key
        item.summary = "a summary" if movie.has_summary else ""
        item.thumb = "/poster.jpg" if movie.has_poster else None
        item.guid = "plex://movie/xxx" if movie.is_matched else None
        item.collections = [MagicMock(tag=c) for c in movie.collections]
        item.media = []
        for path in movie.files:
            part = MagicMock()
            part.file = path
            part.container = path.rsplit(".", 1)[-1] if "." in path else ""
            media = MagicMock()
            media.parts = [part]
            media.videoResolution = "1080"
            media.bitrate = 5000
            media.videoCodec = "h264"
            item.media.append(media)
        return item

    def _episode_mock(self, episode: FakeEpisode) -> MagicMock:
        ep = MagicMock()
        ep.index = episode.index
        ep.parentIndex = episode.season_index
        ep.grandparentTitle = episode.show_title
        ep.ratingKey = self._new_key()
        ep.media = []
        for path in episode.files:
            part = MagicMock()
            part.file = path
            media = MagicMock()
            media.parts = [part]
            media.videoResolution = "1080"
            media.bitrate = 3000
            media.videoCodec = "h264"
            ep.media.append(media)
        return ep

    def _show_mock(self, show: FakeShowBuilder) -> MagicMock:
        show_mock = MagicMock()
        show_mock.title = show.title
        show_mock.year = show.year
        show_mock.ratingKey = self._new_key()
        season_mocks = []
        for season in show.seasons:
            season_mock = MagicMock()
            season_mock.index = season.index
            season_mock.parentTitle = show.title
            episode_mocks = [self._episode_mock(ep) for ep in season.episodes]
            season_mock.episodes.return_value = episode_mocks
            season_mocks.append(season_mock)
        show_mock.seasons.return_value = season_mocks
        return show_mock

    def build(self) -> MagicMock:
        plex = MagicMock()

        movie_items = [self._movie_mock(m) for m in self._movies]
        show_items = [self._show_mock(s) for s in self._shows]

        movie_lib_raw = MagicMock()
        movie_lib_raw.all.return_value = movie_items
        show_lib_raw = MagicMock()
        show_lib_raw.all.return_value = show_items

        libraries = []
        if movie_items:
            libraries.append(Library(title="Movies", kind="movie", raw=movie_lib_raw))
        if show_items:
            libraries.append(Library(title="TV", kind="show", raw=show_lib_raw))

        plex.iter_libraries.return_value = libraries

        def get_media_files(item):  # type: ignore[no-untyped-def]
            for media in getattr(item, "media", []) or []:
                for part in getattr(media, "parts", []) or []:
                    path = getattr(part, "file", None)
                    if path:
                        yield MediaFile(plex_path=path, rating_key=str(item.ratingKey))

        plex.get_media_files.side_effect = get_media_files
        return plex


def make_ctx(
    fake: PlexFake,
    mappings: list[PathMapping] | None = None,
    filesystem_available: bool | None = None,
    check_config: dict[str, dict[str, object]] | None = None,
) -> ScanContext:
    mappings = mappings or []
    path_mapper = PathMapper(mappings)

    config = MagicMock()
    config.paths.mappings = mappings
    config.checks.config = check_config or {}

    if filesystem_available is None:
        filesystem_available = path_mapper.has_mappings

    return ScanContext(
        plex=fake.build(),
        path_mapper=path_mapper,
        config=config,
        filesystem_available=filesystem_available,
        _sink=FindingsSink(),
    )
