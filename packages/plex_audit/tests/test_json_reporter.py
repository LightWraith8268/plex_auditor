import json
from pathlib import Path

from plex_audit.reporters.json import JsonReporter
from plex_audit.types import Finding, Severity


def test_writes_valid_json_with_findings(tmp_path: Path):
    findings = [
        Finding(
            check_id="orphaned_files",
            severity=Severity.WARN,
            title="Orphaned file",
            subject="/m/x.mkv",
            details={"library": "Movies"},
            file_path=Path("/m/x.mkv"),
            suggested_action="Delete or add to Plex",
        ),
    ]
    output = tmp_path / "r.json"
    JsonReporter().write(findings, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["total"] == 1
    assert "generated_at" in payload
    assert payload["findings"][0]["check_id"] == "orphaned_files"
    assert payload["findings"][0]["severity"] == "WARN"
    assert payload["findings"][0]["file_path"] == "/m/x.mkv"
    assert payload["findings"][0]["details"] == {"library": "Movies"}


def test_empty_findings_valid_json(tmp_path: Path):
    output = tmp_path / "r.json"
    JsonReporter().write([], output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["total"] == 0
    assert payload["findings"] == []


def test_omits_none_optional_fields(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.INFO, title="t", subject="s"),
    ]
    output = tmp_path / "r.json"
    JsonReporter().write(findings, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    record = payload["findings"][0]
    assert "file_path" not in record
    assert "plex_item_id" not in record
    assert "suggested_action" not in record


def test_format_attr():
    assert JsonReporter.format == "json"
