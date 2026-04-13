from pathlib import Path

from plex_audit.types import Category, Finding, Severity


def test_severity_ordering():
    assert Severity.INFO < Severity.WARN < Severity.ERROR


def test_finding_is_frozen_dataclass():
    finding = Finding(
        check_id="missing_episodes",
        severity=Severity.WARN,
        title="Season 3 missing 4 episodes",
        subject="Breaking Bad",
        details={"missing": [5, 6, 7, 9]},
    )
    assert finding.check_id == "missing_episodes"
    assert finding.plex_item_id is None
    assert finding.file_path is None
    assert finding.suggested_action is None


def test_finding_accepts_optional_fields():
    finding = Finding(
        check_id="orphaned_files",
        severity=Severity.INFO,
        title="Orphaned file",
        subject="stray.mkv",
        details={},
        file_path=Path("/media/tv/stray.mkv"),
        suggested_action="Delete or add to Plex library",
    )
    assert finding.file_path == Path("/media/tv/stray.mkv")
    assert finding.suggested_action is not None


def test_category_values():
    assert {c.name for c in Category} == {"MISSING", "METADATA", "FILE_HEALTH", "DUPLICATE"}
