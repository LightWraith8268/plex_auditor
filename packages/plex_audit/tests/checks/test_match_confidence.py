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
