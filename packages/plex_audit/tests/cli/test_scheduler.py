from pathlib import Path

from plex_audit.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _write_config(tmp_path: Path) -> Path:
    body = """
plex: {url: http://x, token: t}
paths: {mappings: []}
checks: {enabled: all, disabled: []}
report: {formats: [md], output_dir: ./r, filename_template: "plex-audit-{timestamp}"}
logging: {level: INFO, file: ./plex-audit.log}
"""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(body, encoding="utf-8")
    return cfg


def test_show_cron_snippet(tmp_path: Path):
    cfg = _write_config(tmp_path)
    result = runner.invoke(app, ["schedule", "--show", "--os", "linux", "--config", str(cfg)])
    assert result.exit_code == 0, result.stdout
    assert "0 3 * * *" in result.stdout
    assert "plex-audit scan" in result.stdout
    assert str(cfg) in result.stdout


def test_show_schtasks_snippet(tmp_path: Path):
    cfg = _write_config(tmp_path)
    result = runner.invoke(app, ["schedule", "--show", "--os", "windows", "--config", str(cfg)])
    assert result.exit_code == 0, result.stdout
    assert "schtasks /Create" in result.stdout
    assert "PlexAudit" in result.stdout
    assert str(cfg) in result.stdout


def test_show_requires_show_flag(tmp_path: Path):
    cfg = _write_config(tmp_path)
    result = runner.invoke(app, ["schedule", "--os", "linux", "--config", str(cfg)])
    assert result.exit_code != 0
