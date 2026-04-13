from pathlib import Path
from unittest.mock import MagicMock

from plex_audit.checks.orphaned_files import VIDEO_EXTENSIONS, OrphanedFilesCheck
from plex_audit.context import FindingsSink, ScanContext
from plex_audit.path_mapper import PathMapper, PathMapping
from plex_audit.plex_client import Library, MediaFile
from plex_audit.types import Severity


def _ctx(tmp_path: Path, plex_files: list[str], mappings: list[PathMapping]) -> ScanContext:
    plex = MagicMock()
    plex.iter_libraries.return_value = [Library(title="TV", kind="show", raw=MagicMock())]

    def fake_items(_lib):
        for idx, plex_path in enumerate(plex_files):
            item = MagicMock()
            item.ratingKey = str(idx)
            part = MagicMock()
            part.file = plex_path
            media = MagicMock()
            media.parts = [part]
            item.media = [media]
            yield item

    for lib in plex.iter_libraries.return_value:
        lib.raw.all = lambda _lib=lib: list(fake_items(_lib))

    def get_media_files(item):
        for media in item.media:
            for part in media.parts:
                yield MediaFile(plex_path=part.file, rating_key=str(item.ratingKey))
    plex.get_media_files.side_effect = get_media_files

    config = MagicMock()
    config.paths.mappings = mappings

    return ScanContext(
        plex=plex,
        path_mapper=PathMapper(mappings),
        config=config,
        filesystem_available=True,
        _sink=FindingsSink(),
    )


def test_finds_files_on_disk_not_in_plex(tmp_path: Path):
    media_root = tmp_path / "tv"
    media_root.mkdir()
    (media_root / "known.mkv").write_text("")
    (media_root / "orphan.mkv").write_text("")
    (media_root / "ignored.txt").write_text("")

    ctx = _ctx(
        tmp_path,
        plex_files=["/media/tv/known.mkv"],
        mappings=[PathMapping(plex="/media/tv", local=str(media_root))],
    )
    list(OrphanedFilesCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].subject.endswith("orphan.mkv")
    assert findings[0].severity == Severity.WARN


def test_skips_non_video_extensions():
    assert ".mkv" in VIDEO_EXTENSIONS
    assert ".mp4" in VIDEO_EXTENSIONS
    assert ".txt" not in VIDEO_EXTENSIONS


def test_emits_nothing_when_no_mappings(tmp_path: Path):
    ctx = _ctx(tmp_path, plex_files=[], mappings=[])
    list(OrphanedFilesCheck().run(ctx))
    assert ctx._sink.all() == []
