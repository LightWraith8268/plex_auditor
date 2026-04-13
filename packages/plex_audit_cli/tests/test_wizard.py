from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from plex_audit.plex_client import Library
from plex_audit_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _fake_plex_with_one_library() -> MagicMock:
    raw = MagicMock()
    raw.locations = ["/media/movies"]
    lib = Library(title="Movies", kind="movie", raw=raw)
    plex = MagicMock()
    plex.iter_libraries.return_value = [lib]
    return plex


def test_wizard_writes_config(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"

    inputs = "\n".join([
        "http://localhost:32400",
        "tkn",
        str(tmp_path / "movies-local"),
        "md,json",
        str(tmp_path / "reports"),
    ]) + "\n"

    with patch("plex_audit_cli.wizard.PlexClient") as plex_cls:
        plex_cls.return_value = _fake_plex_with_one_library()
        result = runner.invoke(app, ["init", "--config", str(cfg_path)], input=inputs)

    assert result.exit_code == 0, result.stdout
    assert cfg_path.exists()
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["plex"]["url"] == "http://localhost:32400"
    assert data["plex"]["token"] == "tkn"
    assert data["paths"]["mappings"][0]["plex"] == "/media/movies"
    assert data["paths"]["mappings"][0]["local"] == str(tmp_path / "movies-local")
    assert data["report"]["formats"] == ["md", "json"]
    assert data["report"]["output_dir"] == str(tmp_path / "reports")


def test_wizard_aborts_when_plex_unreachable(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    inputs = "http://x\nbad-token\n"
    with patch("plex_audit_cli.wizard.PlexClient") as plex_cls:
        plex_cls.return_value.iter_libraries.side_effect = ConnectionError("nope")
        result = runner.invoke(app, ["init", "--config", str(cfg_path)], input=inputs)
    assert result.exit_code != 0
    assert not cfg_path.exists()
