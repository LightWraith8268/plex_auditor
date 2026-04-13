"""Prepend a new section to CHANGELOG.md from conventional-commit subjects."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

_TYPE_PATTERN = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?!?:\s*(?P<subject>.+)$", re.IGNORECASE)

_INCLUDED_TYPES = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
}


def build_section(version: str, iso_date: str, commit_subjects: list[str]) -> str:
    buckets: dict[str, list[str]] = {"Added": [], "Fixed": [], "Changed": []}
    for raw in commit_subjects:
        subject = raw.splitlines()[0].strip()
        match = _TYPE_PATTERN.match(subject)
        if not match:
            continue
        commit_type = match.group("type").lower()
        bucket_name = _INCLUDED_TYPES.get(commit_type)
        if bucket_name is None:
            continue
        buckets[bucket_name].append(match.group("subject").strip())

    lines = [f"## [{version}] - {iso_date}", ""]
    any_content = False
    for bucket_name in ("Added", "Changed", "Fixed"):
        entries = buckets[bucket_name]
        if not entries:
            continue
        any_content = True
        lines.append(f"### {bucket_name}")
        for entry in entries:
            lines.append(f"- {entry}")
        lines.append("")
    if not any_content:
        lines.append("_No user-facing changes._")
        lines.append("")
    return "\n".join(lines)


def prepend_to_changelog(path: Path, new_section: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Changelog\n\n"
    header, _, body = existing.partition("\n\n")
    path.write_text(f"{header}\n\n{new_section}\n{body}".rstrip() + "\n", encoding="utf-8")


def _commits_since(ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", f"{ref}..HEAD", "--format=%s"],
        capture_output=True, text=True, check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--since", required=False, default=None, help="git ref; if omitted, uses latest tag")
    parser.add_argument("--path", default="CHANGELOG.md")
    args = parser.parse_args()

    ref = args.since
    if ref is None:
        tag_result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, check=False,
        )
        tag = tag_result.stdout.strip() if tag_result.returncode == 0 else ""
        if tag:
            ref = tag
        else:
            root_result = subprocess.run(
                ["git", "rev-list", "--max-parents=0", "HEAD"],
                capture_output=True, text=True, check=True,
            )
            ref = root_result.stdout.strip().splitlines()[0]

    commits = _commits_since(ref)
    section = build_section(args.version, date.today().isoformat(), commits)
    prepend_to_changelog(Path(args.path), section)
    print(f"Updated {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
