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
