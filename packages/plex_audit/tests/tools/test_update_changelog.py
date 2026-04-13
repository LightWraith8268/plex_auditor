import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parents[4] / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

from update_changelog import build_section, prepend_to_changelog  # noqa: E402


def test_build_section_filters_and_groups():
    commits = [
        "feat(checks): add duplicates check",
        "feat: add HTML reporter",
        "fix(cli): handle missing config",
        "perf: speed up engine",
        "chore: bump deps",
        "docs: update readme",
        "refactor: extract helper",
    ]
    section = build_section("1.2.0", "2026-04-13", commits)
    assert "## [1.2.0] - 2026-04-13" in section
    assert "### Added" in section
    assert "- add duplicates check" in section
    assert "- add HTML reporter" in section
    assert "### Fixed" in section
    assert "- handle missing config" in section
    assert "### Changed" in section
    assert "- speed up engine" in section
    assert "bump deps" not in section
    assert "update readme" not in section
    assert "extract helper" not in section


def test_build_section_returns_header_only_when_nothing_user_facing():
    section = build_section("0.3.1", "2026-04-13", ["chore: bump deps", "docs: tweak"])
    assert "## [0.3.1] - 2026-04-13" in section
    assert "_No user-facing changes._" in section


def test_prepend_preserves_existing_content(tmp_path: Path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [0.1.0] - 2026-04-01\n- Initial release\n", encoding="utf-8")
    new_section = "## [0.2.0] - 2026-04-13\n### Added\n- new stuff\n"
    prepend_to_changelog(path, new_section)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Changelog")
    assert text.index("[0.2.0]") < text.index("[0.1.0]")
