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
    with patch("plex_audit.checks.ffprobe_integrity.shutil.which", return_value=None):
        list(FfprobeIntegrityCheck().run(ctx))
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR
    assert "ffprobe" in findings[0].title.lower()


def test_reports_corrupt_file(tmp_path: Path):
    ctx = _ctx_with_file(tmp_path, enabled=True)
    with patch("plex_audit.checks.ffprobe_integrity.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plex_audit.checks.ffprobe_integrity.subprocess.run") as run:
        run.return_value.returncode = 1
        run.return_value.stderr = "error: invalid data"
        list(FfprobeIntegrityCheck().run(ctx))
    findings = [f for f in ctx._sink.all() if f.check_id == "ffprobe_integrity"]
    assert any(f.severity == Severity.ERROR and "ok.mkv" in f.subject for f in findings)


def test_no_finding_on_clean_file(tmp_path: Path):
    ctx = _ctx_with_file(tmp_path, enabled=True)
    with patch("plex_audit.checks.ffprobe_integrity.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plex_audit.checks.ffprobe_integrity.subprocess.run") as run:
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
    assert check.parallel_safe is False
