from pathlib import Path

from plex_audit.reporters.html import HtmlReporter
from plex_audit.types import Finding, Severity


def test_renders_header_and_counts(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.WARN, title="t", subject="thing"),
        Finding(check_id="c", severity=Severity.ERROR, title="t", subject="oof"),
    ]
    output = tmp_path / "r.html"
    HtmlReporter().write(findings, output)
    html = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Plex Audit Report" in html
    assert "Total findings: 2" in html
    assert "thing" in html
    assert "oof" in html


def test_escapes_html_in_finding_fields(tmp_path: Path):
    findings = [Finding(check_id="c", severity=Severity.INFO, title="<script>alert(1)</script>", subject="s")]
    output = tmp_path / "r.html"
    HtmlReporter().write(findings, output)
    html = output.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_findings_renders_clean_message(tmp_path: Path):
    output = tmp_path / "r.html"
    HtmlReporter().write([], output)
    html = output.read_text(encoding="utf-8")
    assert "No findings" in html


def test_severity_sections_ordered(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.INFO, title="t", subject="i"),
        Finding(check_id="c", severity=Severity.ERROR, title="t", subject="e"),
    ]
    output = tmp_path / "r.html"
    HtmlReporter().write(findings, output)
    html = output.read_text(encoding="utf-8")
    assert html.index("ERROR") < html.index("INFO")


def test_format_attr():
    assert HtmlReporter.format == "html"
