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
