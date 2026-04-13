"""Decide and apply semver bumps from conventional-commit subjects."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

BumpKind = Literal["major", "minor", "patch"]

_TYPE_PATTERN = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!?):", re.IGNORECASE)


def decide_bump(commit_messages: list[str]) -> BumpKind | None:
    highest: BumpKind | None = None
    for message in commit_messages:
        subject = message.splitlines()[0] if message else ""
        body = "\n".join(message.splitlines()[1:]) if message else ""

        match = _TYPE_PATTERN.match(subject)
        if not match:
            continue
        commit_type = match.group("type").lower()
        is_breaking = bool(match.group("breaking")) or "BREAKING CHANGE" in body

        if is_breaking:
            return "major"
        if commit_type == "feat":
            if highest != "minor":
                highest = "minor"
        elif commit_type in ("fix", "perf") and highest is None:
            highest = "patch"
    return highest


def apply_bump(current: str, bump: BumpKind) -> str:
    major, minor, patch = (int(x) for x in current.split("."))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _read_commits_since(ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", f"{ref}..HEAD", "--format=%B%x1e"],
        capture_output=True, text=True, check=True,
    )
    return [m.strip() for m in result.stdout.split("\x1e") if m.strip()]


def _latest_tag() -> str | None:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _read_current_version() -> str:
    pyproject = Path("packages/plex_audit/pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        raise RuntimeError("version not found in packages/plex_audit/pyproject.toml")
    return match.group(1)


def _write_version(new_version: str) -> None:
    for path in (
        Path("packages/plex_audit/pyproject.toml"),
        Path("packages/plex_audit_cli/pyproject.toml"),
        Path("packages/plex_audit/src/plex_audit/__init__.py"),
        Path("packages/plex_audit_cli/src/plex_audit_cli/__init__.py"),
    ):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r'(^version\s*=\s*")[^"]+(")', rf'\g<1>{new_version}\g<2>', text, count=1, flags=re.MULTILINE)
        text = re.sub(r'(__version__\s*=\s*")[^"]+(")', rf'\g<1>{new_version}\g<2>', text, count=1)
        path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tag = _latest_tag()
    ref = tag if tag is not None else "HEAD~50"
    commits = _read_commits_since(ref)
    bump = decide_bump(commits)
    if bump is None:
        print("No version bump needed.", file=sys.stderr)
        return 0

    current = _read_current_version()
    new_version = apply_bump(current, bump)
    print(new_version)

    if not args.dry_run:
        _write_version(new_version)

    return 0


if __name__ == "__main__":
    sys.exit(main())
