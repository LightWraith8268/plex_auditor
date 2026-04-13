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
