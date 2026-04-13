# Plan 2: Check Catalog — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the remaining nine built-in checks (the v1 catalog minus `orphaned_files`, which landed in Plan 1), plus a shared test-fixture helper so every check's tests stay small and readable.

**Architecture:** Each check lives in `packages/plex_audit/src/plex_audit/checks/<id>.py` and implements the `Check` protocol. Each check's tests live in `packages/plex_audit/tests/checks/test_<id>.py` and lean on a shared `PlexFake` builder in `packages/plex_audit/tests/checks/conftest.py`. Checks that need per-check config read it via `ctx.config.checks.config.get(self.id, {})`. Every check registers as an entry point in `packages/plex_audit/pyproject.toml`.

**Tech Stack:** Same as Plan 1 — Python 3.11+, pytest, pydantic v2, python-plexapi (via `PlexClient`).

**Scope note:** The design spec's `incomplete_collections` check needs external metadata (TMDB/Radarr) to determine whether a collection is actually "incomplete." Without that data source, any implementation produces false positives. Deferring to the future `plex_audit_arrs` plugin package.

---

## File Structure

```
packages/plex_audit/
├── src/plex_audit/checks/
│   ├── (existing) orphaned_files.py
│   ├── missing_episodes.py           # Task 2
│   ├── unmatched_items.py            # Task 3
│   ├── missing_artwork.py            # Task 4
│   ├── match_confidence.py           # Task 5
│   ├── missing_files.py              # Task 6
│   ├── quality_threshold.py          # Task 7
│   ├── ffprobe_integrity.py          # Task 8
│   ├── duplicates.py                 # Task 9
│   └── near_duplicates.py            # Task 10
├── tests/checks/
│   ├── conftest.py                   # Task 1 — PlexFake builder + ctx helper
│   ├── (existing) test_orphaned_files.py
│   └── test_<id>.py × 9
└── pyproject.toml                    # entry points grow task by task
```

---

## Task 1: Shared test fixtures (PlexFake builder + ctx helper)

**Files:**
- Create: `packages/plex_audit/tests/checks/conftest.py`

Purpose: every check test needs a fake `PlexClient` that yields libraries, shows, seasons, episodes, and movies with configurable attributes. Rather than rebuilding `MagicMock` chains in every test, we centralize a `PlexFake` builder. This replaces the ad-hoc mock setup currently inlined in `test_orphaned_files.py`.

- [ ] **Step 1: Write the failing test**

Create `packages/plex_audit/tests/checks/conftest.py` tests would fail, so instead, create a sanity test in `packages/plex_audit/tests/checks/test_conftest_helpers.py`:

```python
from plex_audit.path_mapper import PathMapping
from plex_audit.plex_client import MediaFile

from .conftest import PlexFake, make_ctx


def test_plex_fake_yields_movies():
    fake = PlexFake()
    fake.add_movie(title="Inception", year=2010, files=["/media/movies/Inception (2010)/Inception.mkv"])
    plex = fake.build()
    libraries = list(plex.iter_libraries())
    assert any(lib.kind == "movie" for lib in libraries)
    movie_library = next(lib for lib in libraries if lib.kind == "movie")
    items = list(movie_library.raw.all())
    assert items[0].title == "Inception"
    assert items[0].year == 2010
    files = list(plex.get_media_files(items[0]))
    assert files == [MediaFile(plex_path="/media/movies/Inception (2010)/Inception.mkv", rating_key=items[0].ratingKey)]


def test_plex_fake_yields_shows_with_seasons_and_episodes():
    fake = PlexFake()
    show = fake.add_show(title="Breaking Bad")
    show.add_season(number=1, episodes=[(1, ["/media/tv/BB/S01E01.mkv"]), (2, ["/media/tv/BB/S01E02.mkv"])])
    plex = fake.build()
    show_library = next(lib for lib in plex.iter_libraries() if lib.kind == "show")
    shows = list(show_library.raw.all())
    assert shows[0].title == "Breaking Bad"
    seasons = list(shows[0].seasons())
    assert seasons[0].index == 1
    episodes = list(seasons[0].episodes())
    assert [ep.index for ep in episodes] == [1, 2]


def test_make_ctx_wires_path_mapper_and_flags():
    fake = PlexFake()
    ctx = make_ctx(fake, mappings=[PathMapping(plex="/media", local="/local")])
    assert ctx.filesystem_available is True
    assert ctx.path_mapper.to_local("/media/x.mkv") is not None
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/checks/test_conftest_helpers.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `conftest.py`**

```python
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
    """Builder for a fake PlexClient suitable for check tests."""

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

        def get_media_files(item):
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
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/checks/test_conftest_helpers.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Ensure existing test still passes**

Run: `uv run pytest -v`
Expected: all 45 + 3 = 48 tests pass.

- [ ] **Step 6: Ruff + mypy**

Run: `uv run ruff check . && uv run mypy packages/plex_audit/src`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/plex_audit/tests/checks/conftest.py packages/plex_audit/tests/checks/test_conftest_helpers.py
git commit -m "test(checks): add PlexFake builder and make_ctx helper for check tests"
```

---

## Task 2: `missing_episodes` check — episode gaps within downloaded seasons

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/missing_episodes.py`
- Create: `packages/plex_audit/tests/checks/test_missing_episodes.py`
- Modify: `packages/plex_audit/pyproject.toml` (register entry point)

Detects integer gaps in episode indexes within a season the user has started downloading. Example: episodes 1, 2, 4, 5 → episode 3 is missing. Emits one WARN finding per gap, listing the missing episode numbers.

- [ ] **Step 1: Write failing tests**

`packages/plex_audit/tests/checks/test_missing_episodes.py`:

```python
from plex_audit.checks.missing_episodes import MissingEpisodesCheck
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def test_reports_gap_within_a_season():
    fake = PlexFake()
    show = fake.add_show(title="Breaking Bad")
    show.add_season(
        number=1,
        episodes=[
            (1, ["/media/tv/BB/S01E01.mkv"]),
            (2, ["/media/tv/BB/S01E02.mkv"]),
            (4, ["/media/tv/BB/S01E04.mkv"]),
        ],
    )
    ctx = make_ctx(fake)
    list(MissingEpisodesCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == Severity.WARN
    assert "Breaking Bad" in finding.subject
    assert finding.details["season"] == 1
    assert finding.details["missing"] == [3]


def test_no_finding_when_season_is_contiguous():
    fake = PlexFake()
    show = fake.add_show(title="Show A")
    show.add_season(number=1, episodes=[(1, []), (2, []), (3, [])])
    ctx = make_ctx(fake)
    list(MissingEpisodesCheck().run(ctx))
    assert ctx._sink.all() == []


def test_multiple_seasons_each_checked_independently():
    fake = PlexFake()
    show = fake.add_show(title="Show B")
    show.add_season(number=1, episodes=[(1, []), (3, [])])
    show.add_season(number=2, episodes=[(1, []), (2, []), (5, [])])
    ctx = make_ctx(fake)
    list(MissingEpisodesCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 2
    seasons_in_findings = {f.details["season"] for f in findings}
    assert seasons_in_findings == {1, 2}


def test_check_metadata():
    check = MissingEpisodesCheck()
    assert check.id == "missing_episodes"
    assert check.category == Category.MISSING
    assert check.requires_filesystem is False
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/checks/test_missing_episodes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the check**

`packages/plex_audit/src/plex_audit/checks/missing_episodes.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class MissingEpisodesCheck:
    id = "missing_episodes"
    name = "Missing Episodes"
    category = Category.MISSING
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind != "show":
                continue
            for show in library.raw.all():
                for season in show.seasons():
                    indexes = sorted({ep.index for ep in season.episodes()})
                    if len(indexes) < 2:
                        continue
                    expected = set(range(indexes[0], indexes[-1] + 1))
                    missing = sorted(expected - set(indexes))
                    if not missing:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.WARN,
                        title=f"Season {season.index} missing {len(missing)} episode(s)",
                        subject=f"{show.title} — Season {season.index}",
                        details={"season": season.index, "missing": missing, "show": show.title},
                        plex_item_id=str(show.ratingKey),
                        suggested_action="Check Sonarr/download client for missing episodes.",
                    )
                    ctx.report(finding)
                    yield finding
```

- [ ] **Step 4: Register the entry point**

Edit `packages/plex_audit/pyproject.toml`. In the `[project.entry-points."plex_audit.checks"]` section, add:

```toml
missing_episodes = "plex_audit.checks.missing_episodes:MissingEpisodesCheck"
```

- [ ] **Step 5: Re-sync**

Run: `uv sync --all-packages --reinstall-package plex-audit`

- [ ] **Step 6: Run tests**

Run: `uv run pytest packages/plex_audit/tests/checks/test_missing_episodes.py -v`
Expected: PASS (4 tests).

Run: `uv run pytest -v`
Expected: all prior tests still pass.

- [ ] **Step 7: Ruff + mypy**

Clean.

- [ ] **Step 8: Commit**

```bash
git add packages/plex_audit/src/plex_audit/checks/missing_episodes.py packages/plex_audit/tests/checks/test_missing_episodes.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add missing_episodes check"
```

---

## Task 3: `unmatched_items` check — items Plex couldn't match to an agent

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/unmatched_items.py`
- Create: `packages/plex_audit/tests/checks/test_unmatched_items.py`
- Modify: `packages/plex_audit/pyproject.toml`

Plex sets a GUID (`guid` attribute) on matched items. Items with no GUID or a GUID beginning with `local://` are unmatched. Report them.

- [ ] **Step 1: Write failing tests**

`packages/plex_audit/tests/checks/test_unmatched_items.py`:

```python
from plex_audit.checks.unmatched_items import UnmatchedItemsCheck
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def test_flags_movies_with_no_match():
    fake = PlexFake()
    fake.add_movie(title="Mystery Movie", is_matched=False)
    fake.add_movie(title="Real Movie", is_matched=True)
    ctx = make_ctx(fake)
    list(UnmatchedItemsCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].subject == "Mystery Movie"
    assert findings[0].severity == Severity.WARN


def test_no_findings_when_all_matched():
    fake = PlexFake()
    fake.add_movie(title="Matched", is_matched=True)
    ctx = make_ctx(fake)
    list(UnmatchedItemsCheck().run(ctx))
    assert ctx._sink.all() == []


def test_metadata():
    check = UnmatchedItemsCheck()
    assert check.id == "unmatched_items"
    assert check.category == Category.METADATA
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/checks/test_unmatched_items.py -v`

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/unmatched_items.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class UnmatchedItemsCheck:
    id = "unmatched_items"
    name = "Unmatched Items"
    category = Category.METADATA
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind not in ("movie", "show"):
                continue
            for item in library.raw.all():
                guid = getattr(item, "guid", None)
                if guid and not str(guid).startswith("local://"):
                    continue
                finding = Finding(
                    check_id=self.id,
                    severity=Severity.WARN,
                    title="Item not matched to any agent",
                    subject=str(item.title),
                    details={"library": library.title, "kind": library.kind},
                    plex_item_id=str(item.ratingKey),
                    suggested_action="Use Plex 'Match…' to pick the correct metadata entry.",
                )
                ctx.report(finding)
                yield finding
```

- [ ] **Step 4: Register entry point in `pyproject.toml`**

```toml
unmatched_items = "plex_audit.checks.unmatched_items:UnmatchedItemsCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
uv run ruff check . && uv run mypy packages/plex_audit/src
git add packages/plex_audit/src/plex_audit/checks/unmatched_items.py packages/plex_audit/tests/checks/test_unmatched_items.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add unmatched_items check"
```

---

## Task 4: `missing_artwork` check — missing posters or summaries

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/missing_artwork.py`
- Create: `packages/plex_audit/tests/checks/test_missing_artwork.py`
- Modify: `packages/plex_audit/pyproject.toml`

Flags items where `thumb` (poster) is missing, or `summary` is empty. One finding per issue (an item missing both gets two findings).

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/checks/test_missing_artwork.py`:

```python
from plex_audit.checks.missing_artwork import MissingArtworkCheck
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def test_flags_missing_poster():
    fake = PlexFake()
    fake.add_movie(title="No Poster", has_poster=False, has_summary=True)
    ctx = make_ctx(fake)
    list(MissingArtworkCheck().run(ctx))
    subjects = {f.details["issue"] for f in ctx._sink.all()}
    assert subjects == {"poster"}


def test_flags_missing_summary():
    fake = PlexFake()
    fake.add_movie(title="No Summary", has_poster=True, has_summary=False)
    ctx = make_ctx(fake)
    list(MissingArtworkCheck().run(ctx))
    issues = {f.details["issue"] for f in ctx._sink.all()}
    assert issues == {"summary"}


def test_flags_both_missing_with_two_findings():
    fake = PlexFake()
    fake.add_movie(title="Nothing", has_poster=False, has_summary=False)
    ctx = make_ctx(fake)
    list(MissingArtworkCheck().run(ctx))
    issues = sorted(f.details["issue"] for f in ctx._sink.all())
    assert issues == ["poster", "summary"]


def test_no_findings_when_present():
    fake = PlexFake()
    fake.add_movie(title="Complete", has_poster=True, has_summary=True)
    ctx = make_ctx(fake)
    list(MissingArtworkCheck().run(ctx))
    assert ctx._sink.all() == []


def test_metadata():
    check = MissingArtworkCheck()
    assert check.id == "missing_artwork"
    assert check.category == Category.METADATA
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/missing_artwork.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class MissingArtworkCheck:
    id = "missing_artwork"
    name = "Missing Artwork or Summary"
    category = Category.METADATA
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind not in ("movie", "show"):
                continue
            for item in library.raw.all():
                if not getattr(item, "thumb", None):
                    finding = self._finding(item, library.title, "poster")
                    ctx.report(finding)
                    yield finding
                if not (getattr(item, "summary", "") or "").strip():
                    finding = self._finding(item, library.title, "summary")
                    ctx.report(finding)
                    yield finding

    def _finding(self, item: object, library: str, issue: str) -> Finding:
        return Finding(
            check_id=self.id,
            severity=Severity.INFO,
            title=f"Missing {issue}",
            subject=str(getattr(item, "title", "unknown")),
            details={"library": library, "issue": issue},
            plex_item_id=str(getattr(item, "ratingKey", "")),
            suggested_action=f"Add a {issue} in Plex or refresh metadata.",
        )
```

- [ ] **Step 4: Register entry point**

```toml
missing_artwork = "plex_audit.checks.missing_artwork:MissingArtworkCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
git add packages/plex_audit/src/plex_audit/checks/missing_artwork.py packages/plex_audit/tests/checks/test_missing_artwork.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add missing_artwork check"
```

---

## Task 5: `match_confidence` check — year mismatch between filename and Plex metadata

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/match_confidence.py`
- Create: `packages/plex_audit/tests/checks/test_match_confidence.py`
- Modify: `packages/plex_audit/pyproject.toml`

Parses a 4-digit year from the filename (e.g., `Inception (2010).mkv`). If the parsed year differs from Plex's `year` attribute by more than 1 (to allow for release-date vs. production-year slop), emit a WARN. No filename year → skip (no finding).

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/checks/test_match_confidence.py`:

```python
from plex_audit.checks.match_confidence import MatchConfidenceCheck, extract_year_from_path
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def test_extract_year_from_path_finds_parenthesized_year():
    assert extract_year_from_path("/m/Inception (2010)/Inception.mkv") == 2010


def test_extract_year_from_path_finds_bare_year():
    assert extract_year_from_path("/m/Arrival 2016.mkv") == 2016


def test_extract_year_from_path_none_when_absent():
    assert extract_year_from_path("/m/Untitled/file.mkv") is None


def test_flags_year_mismatch():
    fake = PlexFake()
    fake.add_movie(title="Foo", year=2021, files=["/m/Foo (2019)/Foo.mkv"])
    ctx = make_ctx(fake)
    list(MatchConfidenceCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].severity == Severity.WARN
    assert findings[0].details == {"filename_year": 2019, "plex_year": 2021}


def test_no_finding_within_tolerance():
    fake = PlexFake()
    fake.add_movie(title="Foo", year=2020, files=["/m/Foo (2019)/Foo.mkv"])
    ctx = make_ctx(fake)
    list(MatchConfidenceCheck().run(ctx))
    assert ctx._sink.all() == []


def test_no_finding_when_filename_has_no_year():
    fake = PlexFake()
    fake.add_movie(title="Foo", year=2020, files=["/m/Foo/Foo.mkv"])
    ctx = make_ctx(fake)
    list(MatchConfidenceCheck().run(ctx))
    assert ctx._sink.all() == []


def test_metadata():
    check = MatchConfidenceCheck()
    assert check.id == "match_confidence"
    assert check.category == Category.METADATA
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/match_confidence.py`:

```python
from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import PurePosixPath

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

_YEAR_REGEX = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


def extract_year_from_path(path: str) -> int | None:
    name = PurePosixPath(path).name
    parent = PurePosixPath(path).parent.name
    for candidate in (name, parent):
        match = _YEAR_REGEX.search(candidate)
        if match:
            return int(match.group(0))
    return None


class MatchConfidenceCheck:
    id = "match_confidence"
    name = "Match Confidence"
    category = Category.METADATA
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind != "movie":
                continue
            for movie in library.raw.all():
                plex_year = getattr(movie, "year", None)
                if plex_year is None:
                    continue
                for media_file in ctx.plex.get_media_files(movie):
                    file_year = extract_year_from_path(media_file.plex_path)
                    if file_year is None:
                        continue
                    if abs(file_year - plex_year) <= 1:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.WARN,
                        title="Year in filename disagrees with Plex metadata",
                        subject=str(movie.title),
                        details={"filename_year": file_year, "plex_year": plex_year},
                        plex_item_id=str(movie.ratingKey),
                        suggested_action="Verify the match and re-match if incorrect.",
                    )
                    ctx.report(finding)
                    yield finding
                    break  # one finding per movie max
```

- [ ] **Step 4: Register entry point**

```toml
match_confidence = "plex_audit.checks.match_confidence:MatchConfidenceCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
git add packages/plex_audit/src/plex_audit/checks/match_confidence.py packages/plex_audit/tests/checks/test_match_confidence.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add match_confidence check"
```

---

## Task 6: `missing_files` check — Plex references a file, but it's not on disk

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/missing_files.py`
- Create: `packages/plex_audit/tests/checks/test_missing_files.py`
- Modify: `packages/plex_audit/pyproject.toml`

Requires filesystem. For each media file Plex knows, translate to local path via `PathMapper`; if the local path doesn't exist on disk, emit an ERROR finding.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/checks/test_missing_files.py`:

```python
from pathlib import Path

from plex_audit.checks.missing_files import MissingFilesCheck
from plex_audit.path_mapper import PathMapping
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def test_flags_missing_file(tmp_path: Path):
    media_root = tmp_path / "movies"
    media_root.mkdir()
    existing = media_root / "Foo.mkv"
    existing.write_text("")

    fake = PlexFake()
    fake.add_movie(
        title="Foo", year=2020,
        files=[f"/media/movies/Foo.mkv", f"/media/movies/Bar.mkv"],  # Bar doesn't exist
    )
    ctx = make_ctx(fake, mappings=[PathMapping(plex="/media/movies", local=str(media_root))])
    list(MissingFilesCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR
    assert "Bar.mkv" in findings[0].subject


def test_no_finding_when_all_present(tmp_path: Path):
    media_root = tmp_path / "movies"
    media_root.mkdir()
    (media_root / "Foo.mkv").write_text("")

    fake = PlexFake()
    fake.add_movie(title="Foo", year=2020, files=["/media/movies/Foo.mkv"])
    ctx = make_ctx(fake, mappings=[PathMapping(plex="/media/movies", local=str(media_root))])
    list(MissingFilesCheck().run(ctx))
    assert ctx._sink.all() == []


def test_requires_filesystem_flag():
    check = MissingFilesCheck()
    assert check.requires_filesystem is True
    assert check.category == Category.FILE_HEALTH
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/missing_files.py`:

```python
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class MissingFilesCheck:
    id = "missing_files"
    name = "Files Missing on Disk"
    category = Category.FILE_HEALTH
    parallel_safe = True
    requires_filesystem = True

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            for item in library.raw.all():
                for media_file in ctx.plex.get_media_files(item):
                    local = ctx.path_mapper.to_local(media_file.plex_path)
                    if local is None:
                        continue
                    local_path = Path(str(local))
                    if local_path.exists():
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.ERROR,
                        title="File referenced by Plex is missing on disk",
                        subject=media_file.plex_path,
                        details={"library": library.title, "rating_key": media_file.rating_key},
                        plex_item_id=media_file.rating_key,
                        file_path=local_path,
                        suggested_action="Restore the file or remove the entry from Plex.",
                    )
                    ctx.report(finding)
                    yield finding
```

- [ ] **Step 4: Register entry point**

```toml
missing_files = "plex_audit.checks.missing_files:MissingFilesCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
git add packages/plex_audit/src/plex_audit/checks/missing_files.py packages/plex_audit/tests/checks/test_missing_files.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add missing_files check"
```

---

## Task 7: `quality_threshold` check — below configured quality

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/quality_threshold.py`
- Create: `packages/plex_audit/tests/checks/test_quality_threshold.py`
- Modify: `packages/plex_audit/pyproject.toml`

Reads per-check config under `ctx.config.checks.config["quality_threshold"]`. Config keys:
- `min_resolution` — one of `"480"`, `"720"`, `"1080"`, `"2160"`. Default `"1080"`.
- `min_bitrate_kbps` — integer. Default `2000`.
- `allowed_codecs` — list of strings. Default `["h264", "hevc", "av1"]`.

For each media item (movie or episode), check each media variant and report a WARN if any dimension is below threshold.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/checks/test_quality_threshold.py`:

```python
from plex_audit.checks.quality_threshold import QualityThresholdCheck
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def _set_media(movie, resolution: str, bitrate: int, codec: str):
    for media in movie.media:
        media.videoResolution = resolution
        media.bitrate = bitrate
        media.videoCodec = codec


def test_flags_low_resolution():
    fake = PlexFake()
    movie = fake.add_movie(title="LowRes", files=["/m/LowRes.mkv"])
    plex_mock = fake.build()
    # Mutate underlying mock media attributes via the built fake
    ctx = make_ctx(fake)
    # Re-build and override: tweak the first movie's media resolution
    first_lib = next(lib for lib in ctx.plex.iter_libraries() if lib.kind == "movie")
    items = first_lib.raw.all()
    items[0].media[0].videoResolution = "480"
    list(QualityThresholdCheck().run(ctx))
    findings = ctx._sink.all()
    assert any("resolution" in f.details for f in findings)


def test_flags_low_bitrate():
    fake = PlexFake()
    fake.add_movie(title="LowRate", files=["/m/LowRate.mkv"])
    ctx = make_ctx(fake)
    items = next(lib for lib in ctx.plex.iter_libraries() if lib.kind == "movie").raw.all()
    items[0].media[0].bitrate = 500
    list(QualityThresholdCheck().run(ctx))
    assert any("bitrate_kbps" in f.details for f in ctx._sink.all())


def test_flags_disallowed_codec():
    fake = PlexFake()
    fake.add_movie(title="BadCodec", files=["/m/BadCodec.avi"])
    ctx = make_ctx(fake, check_config={"quality_threshold": {"allowed_codecs": ["hevc"]}})
    items = next(lib for lib in ctx.plex.iter_libraries() if lib.kind == "movie").raw.all()
    items[0].media[0].videoCodec = "divx"
    list(QualityThresholdCheck().run(ctx))
    assert any("codec" in f.details for f in ctx._sink.all())


def test_no_finding_when_meets_threshold():
    fake = PlexFake()
    fake.add_movie(title="Good", files=["/m/Good.mkv"])
    ctx = make_ctx(fake)
    list(QualityThresholdCheck().run(ctx))
    assert ctx._sink.all() == []


def test_metadata():
    check = QualityThresholdCheck()
    assert check.id == "quality_threshold"
    assert check.category == Category.FILE_HEALTH
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/quality_threshold.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

_RESOLUTION_ORDER = {"sd": 0, "480": 480, "576": 576, "720": 720, "1080": 1080, "1440": 1440, "2160": 2160, "4k": 2160}


def _resolution_as_int(value: object) -> int:
    if value is None:
        return 0
    s = str(value).lower().strip("p ")
    if s in _RESOLUTION_ORDER:
        return _RESOLUTION_ORDER[s]
    try:
        return int(s)
    except ValueError:
        return 0


class QualityThresholdCheck:
    id = "quality_threshold"
    name = "Quality Threshold"
    category = Category.FILE_HEALTH
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        cfg = ctx.config.checks.config.get(self.id, {})
        min_res = _resolution_as_int(cfg.get("min_resolution", "1080"))
        min_bitrate = int(cfg.get("min_bitrate_kbps", 2000))
        allowed_codecs = {c.lower() for c in cfg.get("allowed_codecs", ["h264", "hevc", "av1"])}

        for library in ctx.plex.iter_libraries():
            if library.kind not in ("movie", "show"):
                continue
            for item in self._iter_playable(library):
                for media in getattr(item, "media", []) or []:
                    issues = {}
                    if _resolution_as_int(getattr(media, "videoResolution", None)) < min_res:
                        issues["resolution"] = getattr(media, "videoResolution", None)
                    if int(getattr(media, "bitrate", 0) or 0) < min_bitrate:
                        issues["bitrate_kbps"] = getattr(media, "bitrate", 0)
                    codec = str(getattr(media, "videoCodec", "")).lower()
                    if codec and codec not in allowed_codecs:
                        issues["codec"] = codec
                    if not issues:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.WARN,
                        title="Below quality threshold",
                        subject=str(getattr(item, "title", getattr(item, "grandparentTitle", "unknown"))),
                        details=issues,
                        plex_item_id=str(getattr(item, "ratingKey", "")),
                        suggested_action="Consider upgrading the source.",
                    )
                    ctx.report(finding)
                    yield finding

    def _iter_playable(self, library):
        if library.kind == "movie":
            yield from library.raw.all()
        else:
            for show in library.raw.all():
                for season in show.seasons():
                    yield from season.episodes()
```

- [ ] **Step 4: Register entry point**

```toml
quality_threshold = "plex_audit.checks.quality_threshold:QualityThresholdCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
git add packages/plex_audit/src/plex_audit/checks/quality_threshold.py packages/plex_audit/tests/checks/test_quality_threshold.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add quality_threshold check with configurable res/bitrate/codec"
```

---

## Task 8: `ffprobe_integrity` check — unplayable files (opt-in)

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/ffprobe_integrity.py`
- Create: `packages/plex_audit/tests/checks/test_ffprobe_integrity.py`
- Modify: `packages/plex_audit/pyproject.toml`

Off by default. Reads config `ctx.config.checks.config["ffprobe_integrity"]["enabled"]` — if falsy, skip. Otherwise, for each known local file, run `ffprobe -v error -of json <path>` and flag files where ffprobe exits non-zero. Emits an ERROR if `ffprobe` isn't installed (and self-disables for the run).

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/checks/test_ffprobe_integrity.py`:

```python
from pathlib import Path
from unittest.mock import patch

from plex_audit.checks.ffprobe_integrity import FfprobeIntegrityCheck
from plex_audit.path_mapper import PathMapping
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def _ctx_with_file(tmp_path: Path, enabled: bool):
    media_root = tmp_path / "m"
    media_root.mkdir()
    (media_root / "ok.mkv").write_text("x")

    fake = PlexFake()
    fake.add_movie(title="Ok", files=["/m/ok.mkv"])
    return make_ctx(
        fake,
        mappings=[PathMapping(plex="/m", local=str(media_root))],
        check_config={"ffprobe_integrity": {"enabled": enabled}},
    )


def test_noop_when_disabled(tmp_path: Path):
    ctx = _ctx_with_file(tmp_path, enabled=False)
    list(FfprobeIntegrityCheck().run(ctx))
    assert ctx._sink.all() == []


def test_reports_when_ffprobe_binary_missing(tmp_path: Path):
    ctx = _ctx_with_file(tmp_path, enabled=True)
    with patch("shutil.which", return_value=None):
        list(FfprobeIntegrityCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR
    assert "ffprobe" in findings[0].title.lower()


def test_reports_corrupt_file(tmp_path: Path):
    ctx = _ctx_with_file(tmp_path, enabled=True)
    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run") as run:
        run.return_value.returncode = 1
        run.return_value.stderr = "error: invalid data"
        list(FfprobeIntegrityCheck().run(ctx))
    findings = [f for f in ctx._sink.all() if f.check_id == "ffprobe_integrity"]
    assert any(f.severity == Severity.ERROR and "ok.mkv" in f.subject for f in findings)


def test_no_finding_on_clean_file(tmp_path: Path):
    ctx = _ctx_with_file(tmp_path, enabled=True)
    with patch("shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stderr = ""
        list(FfprobeIntegrityCheck().run(ctx))
    findings = [f for f in ctx._sink.all() if f.check_id == "ffprobe_integrity"]
    assert findings == []


def test_metadata():
    check = FfprobeIntegrityCheck()
    assert check.id == "ffprobe_integrity"
    assert check.category == Category.FILE_HEALTH
    assert check.requires_filesystem is True
    assert check.parallel_safe is False  # subprocess-bound, don't spawn many
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/ffprobe_integrity.py`:

```python
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class FfprobeIntegrityCheck:
    id = "ffprobe_integrity"
    name = "FFprobe Integrity"
    category = Category.FILE_HEALTH
    parallel_safe = False
    requires_filesystem = True

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        cfg = ctx.config.checks.config.get(self.id, {})
        if not cfg.get("enabled", False):
            return

        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path is None:
            finding = Finding(
                check_id=self.id,
                severity=Severity.ERROR,
                title="ffprobe binary not found; integrity check disabled",
                subject="ffprobe_integrity",
                suggested_action="Install ffmpeg/ffprobe or disable this check.",
            )
            ctx.report(finding)
            yield finding
            return

        for library in ctx.plex.iter_libraries():
            for item in self._iter_playable(library):
                for media_file in ctx.plex.get_media_files(item):
                    local = ctx.path_mapper.to_local(media_file.plex_path)
                    if local is None:
                        continue
                    local_path = Path(str(local))
                    if not local_path.exists():
                        continue
                    result = subprocess.run(
                        [ffprobe_path, "-v", "error", "-of", "json", str(local_path)],
                        capture_output=True, text=True, check=False,
                    )
                    if result.returncode == 0:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.ERROR,
                        title="ffprobe reported errors reading file",
                        subject=str(local_path),
                        details={"stderr": (result.stderr or "").strip()[:500]},
                        plex_item_id=media_file.rating_key,
                        file_path=local_path,
                        suggested_action="Inspect the file; consider re-sourcing.",
                    )
                    ctx.report(finding)
                    yield finding

    def _iter_playable(self, library):
        if library.kind == "movie":
            yield from library.raw.all()
        elif library.kind == "show":
            for show in library.raw.all():
                for season in show.seasons():
                    yield from season.episodes()
```

- [ ] **Step 4: Register entry point**

```toml
ffprobe_integrity = "plex_audit.checks.ffprobe_integrity:FfprobeIntegrityCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
git add packages/plex_audit/src/plex_audit/checks/ffprobe_integrity.py packages/plex_audit/tests/checks/test_ffprobe_integrity.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add opt-in ffprobe_integrity check"
```

---

## Task 9: `duplicates` check — same item with multiple file versions

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/duplicates.py`
- Create: `packages/plex_audit/tests/checks/test_duplicates.py`
- Modify: `packages/plex_audit/pyproject.toml`

Flags Plex items that have more than one `media` entry (i.e., the same movie/episode with multiple file variants). INFO severity; includes all file paths in `details`.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/checks/test_duplicates.py`:

```python
from unittest.mock import MagicMock

from plex_audit.checks.duplicates import DuplicatesCheck
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def _attach_extra_media(item, path: str) -> None:
    part = MagicMock()
    part.file = path
    media = MagicMock()
    media.parts = [part]
    item.media.append(media)


def test_flags_item_with_two_file_variants():
    fake = PlexFake()
    fake.add_movie(title="Inception", files=["/m/Inception 1080p.mkv"])
    ctx = make_ctx(fake)
    items = next(lib for lib in ctx.plex.iter_libraries() if lib.kind == "movie").raw.all()
    _attach_extra_media(items[0], "/m/Inception 720p.mkv")
    list(DuplicatesCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].severity == Severity.INFO
    assert len(findings[0].details["files"]) == 2


def test_no_finding_for_single_file():
    fake = PlexFake()
    fake.add_movie(title="Solo", files=["/m/Solo.mkv"])
    ctx = make_ctx(fake)
    list(DuplicatesCheck().run(ctx))
    assert ctx._sink.all() == []


def test_metadata():
    check = DuplicatesCheck()
    assert check.id == "duplicates"
    assert check.category == Category.DUPLICATE
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/duplicates.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class DuplicatesCheck:
    id = "duplicates"
    name = "Duplicate Media Files"
    category = Category.DUPLICATE
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            for item in self._iter_playable(library):
                files = [mf.plex_path for mf in ctx.plex.get_media_files(item)]
                if len(files) < 2:
                    continue
                finding = Finding(
                    check_id=self.id,
                    severity=Severity.INFO,
                    title=f"{len(files)} file variants for one item",
                    subject=str(getattr(item, "title", getattr(item, "grandparentTitle", "unknown"))),
                    details={"files": files, "library": library.title},
                    plex_item_id=str(getattr(item, "ratingKey", "")),
                    suggested_action="Keep the best quality; delete others if desired.",
                )
                ctx.report(finding)
                yield finding

    def _iter_playable(self, library):
        if library.kind == "movie":
            yield from library.raw.all()
        elif library.kind == "show":
            for show in library.raw.all():
                for season in show.seasons():
                    yield from season.episodes()
```

- [ ] **Step 4: Register entry point**

```toml
duplicates = "plex_audit.checks.duplicates:DuplicatesCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
git add packages/plex_audit/src/plex_audit/checks/duplicates.py packages/plex_audit/tests/checks/test_duplicates.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add duplicates check for items with multiple file variants"
```

---

## Task 10: `near_duplicates` check — same title, different editions/years

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/near_duplicates.py`
- Create: `packages/plex_audit/tests/checks/test_near_duplicates.py`
- Modify: `packages/plex_audit/pyproject.toml`

Within a movie library, group items by normalized title (case-insensitive, punctuation-stripped). If a group has 2+ distinct Plex items (different rating keys, possibly different years), flag as near-duplicates. INFO severity.

Respects `ctx.config.checks.config["near_duplicates"]["ignore_editions"]` (default `False`) — when True, strip edition markers (`(Director's Cut)`, `[Extended]`) before normalization so "Blade Runner" and "Blade Runner (Director's Cut)" collapse to the same group.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/checks/test_near_duplicates.py`:

```python
from plex_audit.checks.near_duplicates import NearDuplicatesCheck, normalize_title
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def test_normalize_title_strips_punctuation_and_case():
    assert normalize_title("Blade Runner!") == "blade runner"
    assert normalize_title("The Thing (1982)") == "the thing"


def test_normalize_title_strips_editions_when_requested():
    assert normalize_title("Blade Runner (Director's Cut)", strip_editions=True) == "blade runner"
    assert normalize_title("Dune [Extended]", strip_editions=True) == "dune"


def test_flags_two_movies_sharing_normalized_title():
    fake = PlexFake()
    fake.add_movie(title="The Thing", year=1982, files=["/m/1982/Thing.mkv"])
    fake.add_movie(title="The Thing", year=2011, files=["/m/2011/Thing.mkv"])
    ctx = make_ctx(fake)
    list(NearDuplicatesCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].severity == Severity.INFO
    assert len(findings[0].details["items"]) == 2


def test_does_not_flag_distinct_titles():
    fake = PlexFake()
    fake.add_movie(title="Arrival", year=2016)
    fake.add_movie(title="Interstellar", year=2014)
    ctx = make_ctx(fake)
    list(NearDuplicatesCheck().run(ctx))
    assert ctx._sink.all() == []


def test_editions_collapse_when_ignore_editions_true():
    fake = PlexFake()
    fake.add_movie(title="Blade Runner", year=1982)
    fake.add_movie(title="Blade Runner (Director's Cut)", year=1992)
    ctx = make_ctx(fake, check_config={"near_duplicates": {"ignore_editions": True}})
    list(NearDuplicatesCheck().run(ctx))
    assert len(ctx._sink.all()) == 1


def test_editions_do_not_collapse_by_default():
    fake = PlexFake()
    fake.add_movie(title="Blade Runner", year=1982)
    fake.add_movie(title="Blade Runner (Director's Cut)", year=1992)
    ctx = make_ctx(fake)
    list(NearDuplicatesCheck().run(ctx))
    assert ctx._sink.all() == []


def test_metadata():
    check = NearDuplicatesCheck()
    assert check.id == "near_duplicates"
    assert check.category == Category.DUPLICATE
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

`packages/plex_audit/src/plex_audit/checks/near_duplicates.py`:

```python
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

_EDITION_REGEX = re.compile(r"[\(\[][^\)\]]*(cut|edition|extended|remaster|imax|director|theatrical)[^\)\]]*[\)\]]", re.IGNORECASE)
_YEAR_REGEX = re.compile(r"[\(\[]?\b(19|20)\d{2}\b[\)\]]?")
_PUNCT_REGEX = re.compile(r"[^\w\s]")


def normalize_title(title: str, strip_editions: bool = False) -> str:
    working = title
    if strip_editions:
        working = _EDITION_REGEX.sub("", working)
    working = _YEAR_REGEX.sub("", working)
    working = _PUNCT_REGEX.sub("", working)
    return " ".join(working.lower().split())


class NearDuplicatesCheck:
    id = "near_duplicates"
    name = "Near-Duplicate Titles"
    category = Category.DUPLICATE
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        cfg = ctx.config.checks.config.get(self.id, {})
        strip_editions = bool(cfg.get("ignore_editions", False))

        for library in ctx.plex.iter_libraries():
            if library.kind != "movie":
                continue
            groups: dict[str, list[object]] = defaultdict(list)
            for movie in library.raw.all():
                key = normalize_title(str(movie.title), strip_editions=strip_editions)
                groups[key].append(movie)

            for key, members in groups.items():
                if len(members) < 2:
                    continue
                finding = Finding(
                    check_id=self.id,
                    severity=Severity.INFO,
                    title=f"{len(members)} items share a normalized title",
                    subject=key,
                    details={
                        "items": [
                            {"title": getattr(m, "title", ""), "year": getattr(m, "year", None), "rating_key": str(getattr(m, "ratingKey", ""))}
                            for m in members
                        ],
                        "library": library.title,
                    },
                    suggested_action="Verify these are intentional (e.g., remakes) or merge/remove.",
                )
                ctx.report(finding)
                yield finding
```

- [ ] **Step 4: Register entry point**

```toml
near_duplicates = "plex_audit.checks.near_duplicates:NearDuplicatesCheck"
```

- [ ] **Step 5: Sync, test, lint, commit**

```bash
uv sync --all-packages --reinstall-package plex-audit
uv run pytest -v
git add packages/plex_audit/src/plex_audit/checks/near_duplicates.py packages/plex_audit/tests/checks/test_near_duplicates.py packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add near_duplicates check with optional edition-stripping"
```

---

## Self-review notes

- Spec coverage: Plan 2 delivers 9 of the spec's 11 listed checks. `orphaned_files` shipped in Plan 1. `incomplete_collections` is deferred to the future `plex_audit_arrs` plugin because it requires external metadata to distinguish "collection intentionally has 2 movies" from "collection is missing entries." "Missing latest aired episodes" was already scoped to the *arrs plugin in the spec.
- Placeholder scan: each task spells out test code, production code, entry-point line, and commit message. No TBD/TODO.
- Type consistency: every check implements `id/name/category/parallel_safe/requires_filesystem` attributes and a `run(ctx)` generator that calls `ctx.report(finding)` and `yield`s the same finding (the Plan 1 dual-report pattern, needed so tests that call `list(check.run(ctx))` see findings via the sink).
- Shared `PlexFake` (Task 1) is declared stable for every subsequent task. Tasks 2–10 only use methods defined on `PlexFake` and `make_ctx` in Task 1.
