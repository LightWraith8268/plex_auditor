from pathlib import Path
from unittest.mock import MagicMock, patch

from plex_audit_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _make_library_with_one_known_file(known_plex_path: str):
    part = MagicMock()
    part.file = known_plex_path
    media = MagicMock()
    media.parts = [part]
    item = MagicMock()
    item.media = [media]
    item.ratingKey = "1"

    library = MagicMock()
    library.kind = "show"
    library.title = "TV"
    library.raw.all.return_value = [item]
    return library


def test_end_to_end_detects_orphan_and_writes_report(tmp_path: Path):
    media_root = tmp_path / "tv"
    media_root.mkdir()
    known = media_root / "known.mkv"
    known.write_text("")
    orphan = media_root / "orphan.mkv"
    orphan.write_text("")

    # Plex reports POSIX paths. Map /media/tv → the local media_root.
    config_body = f"""
plex:
  url: http://x
  token: t
paths:
  mappings:
    - plex: /media/tv
      local: {media_root.as_posix()}
checks:
  enabled: all
  disabled: []
report:
  formats: [md]
  output_dir: {(tmp_path / "reports").as_posix()}
  filename_template: "plex-audit-{{timestamp}}"
logging:
  level: INFO
  file: {(tmp_path / "plex-audit.log").as_posix()}
"""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(config_body, encoding="utf-8")

    # Plex "knows about" /media/tv/known.mkv. It does NOT know /media/tv/orphan.mkv.
    library = _make_library_with_one_known_file("/media/tv/known.mkv")

    with patch("plex_audit_cli.main.PlexClient") as plex_cls:
        instance = plex_cls.return_value
        instance.iter_libraries.return_value = [library]

        def get_media_files(item):
            from plex_audit.plex_client import MediaFile
            for media in item.media:
                for part in media.parts:
                    yield MediaFile(plex_path=part.file, rating_key=str(item.ratingKey))
        instance.get_media_files.side_effect = get_media_files

        result = runner.invoke(app, ["scan", "--config", str(cfg)])

    assert result.exit_code == 1, result.stdout  # one WARN finding for the orphan
    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "orphan.mkv" in text
    assert "known.mkv" not in text
