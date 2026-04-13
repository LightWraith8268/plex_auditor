from pathlib import Path

import pytest
from plex_audit.config import Config, ConfigError, load_config

SAMPLE_YAML = """
plex:
  url: http://localhost:32400
  token: abc123
  verify_ssl: true
  timeout_seconds: 30

paths:
  mappings:
    - plex: /media/tv
      local: D:/Media/TV

checks:
  enabled: all
  disabled: []
  config: {}

report:
  formats: [md]
  output_dir: ./reports
  filename_template: "plex-audit-{timestamp}"

logging:
  level: INFO
  file: ./plex-audit.log
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_minimal_valid_config(tmp_path: Path):
    cfg = load_config(_write(tmp_path, SAMPLE_YAML))
    assert isinstance(cfg, Config)
    assert cfg.plex.url == "http://localhost:32400"
    assert cfg.plex.token == "abc123"
    assert cfg.paths.mappings[0].plex == "/media/tv"
    assert cfg.report.formats == ["md"]


def test_env_var_overrides_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLEX_AUDIT_PLEX__TOKEN", "env-token")
    cfg = load_config(_write(tmp_path, SAMPLE_YAML))
    assert cfg.plex.token == "env-token"


def test_cli_overrides_beat_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLEX_AUDIT_PLEX__URL", "http://env:32400")
    cfg = load_config(
        _write(tmp_path, SAMPLE_YAML),
        overrides={"plex": {"url": "http://cli:32400"}},
    )
    assert cfg.plex.url == "http://cli:32400"


def test_missing_required_field_raises(tmp_path: Path):
    body = SAMPLE_YAML.replace("token: abc123", "")
    with pytest.raises(ConfigError) as info:
        load_config(_write(tmp_path, body))
    assert "token" in str(info.value)


def test_enabled_accepts_list_or_all(tmp_path: Path):
    cfg = load_config(_write(tmp_path, SAMPLE_YAML.replace("enabled: all", "enabled: [orphaned_files]")))
    assert cfg.checks.enabled == ["orphaned_files"]


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")
