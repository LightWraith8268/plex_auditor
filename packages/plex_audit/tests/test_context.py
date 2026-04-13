from unittest.mock import MagicMock

from plex_audit.context import FindingsSink, ScanContext
from plex_audit.types import Finding, Severity


def _finding(check_id: str = "c", severity: Severity = Severity.WARN, subject: str = "s") -> Finding:
    return Finding(check_id=check_id, severity=severity, title="t", subject=subject)


def test_sink_collects_findings():
    sink = FindingsSink()
    sink.add(_finding())
    sink.add(_finding(check_id="c2"))
    assert len(sink.all()) == 2


def test_sink_deduplicates_identical_findings():
    sink = FindingsSink()
    a = _finding()
    sink.add(a)
    sink.add(a)  # same hash
    assert len(sink.all()) == 1


def test_sink_sorts_by_severity_then_check_then_subject():
    sink = FindingsSink()
    sink.add(_finding(check_id="b", severity=Severity.INFO, subject="z"))
    sink.add(_finding(check_id="a", severity=Severity.ERROR, subject="y"))
    sink.add(_finding(check_id="a", severity=Severity.ERROR, subject="x"))

    ordered = sink.all()
    assert [f.severity for f in ordered] == [Severity.ERROR, Severity.ERROR, Severity.INFO]
    assert [f.subject for f in ordered[:2]] == ["x", "y"]


def test_sink_highest_severity():
    sink = FindingsSink()
    assert sink.highest_severity() is None
    sink.add(_finding(severity=Severity.INFO))
    sink.add(_finding(severity=Severity.WARN, subject="q"))
    assert sink.highest_severity() == Severity.WARN


def test_scan_context_exposes_services_and_report_method():
    sink = FindingsSink()
    ctx = ScanContext(
        plex=MagicMock(),
        path_mapper=MagicMock(has_mappings=True),
        config=MagicMock(),
        filesystem_available=True,
        _sink=sink,
    )
    ctx.report(_finding())
    assert len(sink.all()) == 1
