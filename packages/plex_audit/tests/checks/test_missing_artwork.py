from plex_audit.checks.missing_artwork import MissingArtworkCheck
from plex_audit.types import Category

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
