import sys
from pathlib import Path

# Ensure the tools/ directory is importable for this test.
_TOOLS_DIR = Path(__file__).resolve().parents[4] / "tools"
sys.path.insert(0, str(_TOOLS_DIR))

from bump_version import apply_bump, decide_bump  # noqa: E402


def test_feat_triggers_minor_bump():
    assert decide_bump(["feat: add thing"]) == "minor"


def test_fix_triggers_patch_bump():
    assert decide_bump(["fix: correct thing"]) == "patch"


def test_breaking_change_triggers_major_bump():
    assert decide_bump(["feat!: redesign API"]) == "major"
    assert decide_bump(["feat: add thing\n\nBREAKING CHANGE: wipes the store"]) == "major"


def test_major_wins_over_minor_wins_over_patch():
    assert decide_bump(["fix: a", "feat: b", "feat!: c"]) == "major"
    assert decide_bump(["fix: a", "feat: b"]) == "minor"


def test_chore_and_docs_do_not_bump():
    assert decide_bump(["chore: bump deps", "docs: update readme"]) is None


def test_apply_bump_respects_semver():
    assert apply_bump("0.1.0", "patch") == "0.1.1"
    assert apply_bump("0.1.9", "minor") == "0.2.0"
    assert apply_bump("0.2.3", "major") == "1.0.0"
