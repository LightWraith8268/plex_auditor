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
        files=["/media/movies/Foo.mkv", "/media/movies/Bar.mkv"],
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
