from pathlib import Path
from unittest.mock import patch

from plex_audit.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

CONFIG = """
plex:
  url: http://localhost:32400
  token: t
paths:
  mappings: []
checks:
  enabled: []
  disabled: []
report:
  formats: [md]
  output_dir: "{out}"
  filename_template: "plex-audit-{{timestamp}}"
logging:
  level: INFO
  file: ./plex-audit.log
"""


def _write_config(tmp_path: Path) -> Path:
    out = tmp_path / "reports"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG.format(out=out.as_posix()), encoding="utf-8")
    return cfg


def test_scan_returns_zero_on_clean_run(tmp_path: Path):
    cfg = _write_config(tmp_path)

    with patch("plex_audit.cli.main.PlexClient") as plex_cls:
        plex_cls.return_value.iter_libraries.return_value = []
        result = runner.invoke(app, ["scan", "--config", str(cfg)])

    assert result.exit_code == 0, result.stdout
    report_files = list((tmp_path / "reports").glob("*.md"))
    assert len(report_files) == 1
    assert "No findings" in report_files[0].read_text(encoding="utf-8")


def test_scan_exits_four_on_missing_config(tmp_path: Path):
    result = runner.invoke(app, ["scan", "--config", str(tmp_path / "no.yaml")])
    assert result.exit_code == 4


def test_scan_exits_three_when_plex_unreachable(tmp_path: Path):
    cfg = _write_config(tmp_path)
    with patch("plex_audit.cli.main.PlexClient") as plex_cls:
        plex_cls.return_value.iter_libraries.side_effect = ConnectionError("nope")
        result = runner.invoke(app, ["scan", "--config", str(cfg)])
    assert result.exit_code == 3
