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
