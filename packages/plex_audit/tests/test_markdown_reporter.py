from pathlib import Path

from plex_audit.reporters.markdown import MarkdownReporter
from plex_audit.types import Finding, Severity


def test_renders_header_and_summary(tmp_path: Path):
    findings = [
        Finding(check_id="orphaned_files", severity=Severity.WARN, title="Orphaned file", subject="stray.mkv"),
        Finding(check_id="orphaned_files", severity=Severity.WARN, title="Orphaned file", subject="other.mkv"),
    ]
    output = tmp_path / "r.md"
    MarkdownReporter().write(findings, output)
    text = output.read_text(encoding="utf-8")
    assert "# Plex Audit Report" in text
    assert "**Total findings:** 2" in text
    assert "orphaned_files" in text
    assert "stray.mkv" in text


def test_renders_empty_findings_as_clean(tmp_path: Path):
    output = tmp_path / "r.md"
    MarkdownReporter().write([], output)
    text = output.read_text(encoding="utf-8")
    assert "No findings" in text


def test_severity_sections_are_present(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.ERROR, title="t", subject="s1"),
        Finding(check_id="c", severity=Severity.INFO, title="t", subject="s2"),
    ]
    output = tmp_path / "r.md"
    MarkdownReporter().write(findings, output)
    text = output.read_text(encoding="utf-8")
    assert "## ERROR" in text
    assert "## INFO" in text
    assert text.index("## ERROR") < text.index("## INFO")
