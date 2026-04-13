from plex_audit.checks.quality_threshold import QualityThresholdCheck
from plex_audit.types import Category, Severity

from .conftest import PlexFake, make_ctx


def test_flags_low_resolution():
    fake = PlexFake()
    fake.add_movie(title="LowRes", files=["/m/LowRes.mkv"])
    ctx = make_ctx(fake)
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
