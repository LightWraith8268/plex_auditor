from pathlib import Path
from unittest.mock import patch

from plex_audit.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

CONFIG = """
plex:
  url: http://x
  token: t
paths:
  mappings: []
checks:
  enabled: []
  disabled: []
report:
  formats: [md, json, html]
  output_dir: "{out}"
  filename_template: "plex-audit-{{timestamp}}"
logging:
  level: INFO
  file: ./plex-audit.log
"""


def test_writes_all_three_formats(tmp_path: Path):
    out = tmp_path / "reports"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG.format(out=out.as_posix()), encoding="utf-8")

    with patch("plex_audit.cli.main.PlexClient") as plex_cls:
        plex_cls.return_value.iter_libraries.return_value = []
        result = runner.invoke(app, ["scan", "--config", str(cfg)])

    assert result.exit_code == 0, result.stdout
    assert len(list(out.glob("*.md"))) == 1
    assert len(list(out.glob("*.json"))) == 1
    assert len(list(out.glob("*.html"))) == 1
