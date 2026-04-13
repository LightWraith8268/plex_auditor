# Plan 4: Distribution + Release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `plex-audit` installable by the public three ways (pip, standalone binary, Docker), with an automated release pipeline driven by conventional commits.

**Architecture:** A release runs when `main` advances. A small Python script parses the commit log since the last tag, decides the semver bump, writes `CHANGELOG.md`, tags, and pushes. Downstream jobs (PyPI, binaries, GHCR) key off the tag. Binaries come from PyInstaller on a matrix of OSes. The Docker image is a slim Python base with `ffprobe` baked in, built multi-arch via `docker buildx` and pushed to `ghcr.io/<owner>/plex_auditor`.

**Tech Stack:** GitHub Actions, PyInstaller, `docker buildx`, PyPI "Trusted Publishing" (OIDC — no API token in secrets).

**Manual setup required from the owner (one-time, before the first release can succeed):**
1. Register both packages on PyPI and enable Trusted Publishing — map repo `LightWraith8268/plex_auditor` + workflow `release.yml` to the `plex-audit` and `plex-audit-cli` project pages. See <https://docs.pypi.org/trusted-publishers/>.
2. Ensure `GITHUB_TOKEN` has `packages: write` in the release workflow (already granted per job permissions block).

These are one-time setup steps outside the code. The plan below produces everything else.

---

## File Structure

```
plex_tools/
├── .github/workflows/
│   ├── ci.yml                         # already exists (Plan 1 add-on)
│   ├── auto-merge.yml                 # modify: dispatch release after merge
│   └── release.yml                    # Task 4
├── docker/
│   ├── Dockerfile                     # Task 3
│   └── entrypoint.sh
├── .dockerignore                      # Task 3
├── CHANGELOG.md                       # Task 2 — seeded empty
├── tools/
│   ├── bump_version.py                # Task 1
│   └── update_changelog.py            # Task 2
├── packages/plex_audit/tests/tools/
│   ├── __init__.py
│   ├── test_bump_version.py           # Task 1
│   └── test_update_changelog.py       # Task 2
└── README.md                          # Task 6: installation section
```

---

## Task 1: Version bump script

**Files:**
- Create: `tools/bump_version.py`
- Create: `packages/plex_audit/tests/tools/__init__.py`
- Create: `packages/plex_audit/tests/tools/test_bump_version.py`
- Modify: `pytest.ini` so the new tests directory is collected

Determines the next version from a list of conventional-commit subject lines. Rules:
- Any line starts with `feat!:`, contains `BREAKING CHANGE`, or ends with `!:` on the type → major bump.
- Any `feat:` → minor bump (unless a major was found).
- Any `fix:` / `perf:` → patch bump (unless higher was found).
- Anything else → no bump (`None`).

Also exposes `apply_bump(current: str, bump: Literal["major","minor","patch"]) -> str`.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/tools/__init__.py` — empty.

`packages/plex_audit/tests/tools/test_bump_version.py`:

```python
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
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implementation**

`tools/bump_version.py`:

```python
"""Decide and apply semver bumps from conventional-commit subjects."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

BumpKind = Literal["major", "minor", "patch"]

_TYPE_PATTERN = re.compile(r"^(?P<type>[a-z]+)(?P<breaking>!?):", re.IGNORECASE)


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
    if tag is None:
        print("No prior tag found; treating all commits as eligible.", file=sys.stderr)
        ref = "HEAD~50"  # fallback window
    else:
        ref = tag
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
```

- [ ] **Step 4: Register the new test directory** — edit `pytest.ini` `testpaths`:

Change:
```
testpaths = packages/plex_audit/tests packages/plex_audit_cli/tests
```
to:
```
testpaths = packages/plex_audit/tests packages/plex_audit_cli/tests packages/plex_audit/tests/tools
```

(Actually `packages/plex_audit/tests` already recursively collects; the line above is redundant-but-explicit. Skip if tests are discovered already.)

- [ ] **Step 5: Run tests** — `uv run pytest packages/plex_audit/tests/tools/test_bump_version.py -v` → PASS (6 tests). Full suite should still pass.

- [ ] **Step 6: Ruff + mypy**

`tools/` is not imported by production code, so we add it to the mypy skip list. Edit `mypy.ini` and add:
```
[mypy-tools.*]
ignore_errors = True
```

Actually better: run mypy only on `packages/*/src` as we already do; `tools/` is a sibling and not touched. Just make sure ruff passes. Ruff lint rule B will object to `except Exception as exc` without use — not relevant here.

- [ ] **Step 7: Commit**

```bash
git add tools/bump_version.py packages/plex_audit/tests/tools/
git commit -m "feat(release): add conventional-commits version bump script"
```

---

## Task 2: Changelog generator

**Files:**
- Create: `tools/update_changelog.py`
- Create: `CHANGELOG.md` (seeded empty)
- Create: `packages/plex_audit/tests/tools/test_update_changelog.py`

Produces a changelog section under a new `## [VERSION] - YYYY-MM-DD` heading. Groups entries:
- `### Added` — `feat:` entries (strip `feat:` prefix)
- `### Changed` — `perf:` entries
- `### Fixed` — `fix:` entries

Excludes `chore:`, `ci:`, `build:`, `refactor:`, `docs:`, `test:` from user-facing changelog. A single-line scope prefix like `feat(cli):` is stripped to just the subject text.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/tools/test_update_changelog.py`:

```python
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
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implementation**

`tools/update_changelog.py`:

```python
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
        ref = tag_result.stdout.strip() if tag_result.returncode == 0 and tag_result.stdout.strip() else "HEAD~50"

    commits = _commits_since(ref)
    section = build_section(args.version, date.today().isoformat(), commits)
    prepend_to_changelog(Path(args.path), section)
    print(f"Updated {args.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Seed empty `CHANGELOG.md`**

Create `CHANGELOG.md`:

```markdown
# Changelog

All notable user-facing changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project adheres to [Semantic Versioning](https://semver.org/).
```

- [ ] **Step 5: Run tests, ruff, commit**

```bash
uv run pytest -v
git add tools/update_changelog.py CHANGELOG.md packages/plex_audit/tests/tools/test_update_changelog.py
git commit -m "feat(release): add changelog generator and seed CHANGELOG.md"
```

---

## Task 3: Dockerfile + entrypoint + .dockerignore

**Files:**
- Create: `docker/Dockerfile`
- Create: `docker/entrypoint.sh`
- Create: `.dockerignore`

Base `python:3.12-slim`. Installs `ffmpeg` (provides `ffprobe`). Uses `uv` to install the workspace, then copies the installed bin into the final image. Entrypoint forwards arguments to `plex-audit`, defaulting to `scan`.

- [ ] **Step 1: Create `.dockerignore`**

```
.git
.venv
.venv/
__pycache__
**/__pycache__
.pytest_cache
.ruff_cache
.mypy_cache
*.egg-info
dist
build
reports
docs
.github
tests
**/tests
plex-audit.log
```

- [ ] **Step 2: Create `docker/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS builder
ENV UV_LINK_MODE=copy PATH="/root/.local/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -LsSf https://astral.sh/uv/install.sh | sh \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --no-dev --all-packages

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 1000 plex

COPY --from=builder /src/.venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /config
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER plex
VOLUME ["/config", "/reports"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["scan", "--config", "/config/config.yaml"]
```

- [ ] **Step 3: Create `docker/entrypoint.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
exec plex-audit "$@"
```

- [ ] **Step 4: Local build + smoke test**

Run (you do not need to push):

```bash
docker build -f docker/Dockerfile -t plex-audit:dev .
docker run --rm plex-audit:dev --help
```

Expected: help text listing `scan`, `init`, `schedule`, `version`.

If Docker isn't available locally, skip and report DONE_WITH_CONCERNS — the workflow in Task 4 builds it on a Linux runner anyway.

- [ ] **Step 5: Commit**

```bash
git add docker/ .dockerignore
git commit -m "feat(release): add Dockerfile and entrypoint"
```

---

## Task 4: Release workflow (`.github/workflows/release.yml`)

**Files:**
- Create: `.github/workflows/release.yml`

Triggers: `push` to `main` and `workflow_dispatch`. Jobs run in order (each depends on the previous):

1. `bump` — runs `bump_version.py`, updates `CHANGELOG.md` via `update_changelog.py`, commits `chore(release): v<new>` with `[skip ci]`, tags `v<new>`, pushes both.
2. `github_release` — creates a GitHub Release with the new changelog section body.
3. `pypi` — builds and publishes both packages via Trusted Publishing (`pypa/gh-action-pypi-publish`).
4. `binaries` — matrix of Ubuntu/macOS/Windows; runs PyInstaller; attaches artifacts to the GitHub Release.
5. `docker` — builds multi-arch (`linux/amd64`, `linux/arm64`) via `docker/build-push-action` and pushes `ghcr.io/<owner>/plex_auditor:<version>` and `:latest`.

- [ ] **Step 1: Create `.github/workflows/release.yml`**

```yaml
name: Release

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write
  id-token: write   # for PyPI trusted publishing
  packages: write   # for GHCR

jobs:
  bump:
    name: Determine and apply version bump
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.bump.outputs.version }}
      bumped: ${{ steps.bump.outputs.bumped }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python
        run: uv python install 3.12

      - name: Skip if last commit is a release commit
        id: skipcheck
        run: |
          msg=$(git log -1 --pretty=%s)
          if [[ "$msg" == chore\(release\)* ]]; then
            echo "bumped=false" >> "$GITHUB_OUTPUT"
          else
            echo "bumped=" >> "$GITHUB_OUTPUT"
          fi

      - name: Determine new version
        id: bump
        if: steps.skipcheck.outputs.bumped != 'false'
        run: |
          uv sync --all-packages
          NEW=$(uv run python tools/bump_version.py)
          if [ -z "$NEW" ]; then
            echo "No bump needed."
            echo "bumped=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          echo "version=$NEW" >> "$GITHUB_OUTPUT"
          echo "bumped=true" >> "$GITHUB_OUTPUT"

      - name: Update changelog
        if: steps.bump.outputs.bumped == 'true'
        run: |
          uv run python tools/update_changelog.py --version "${{ steps.bump.outputs.version }}"

      - name: Commit, tag, push
        if: steps.bump.outputs.bumped == 'true'
        env:
          VERSION: ${{ steps.bump.outputs.version }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add packages/ CHANGELOG.md
          git commit -m "chore(release): v$VERSION [skip ci]"
          git tag "v$VERSION"
          git push origin main
          git push origin "v$VERSION"

  github_release:
    name: Create GitHub Release
    needs: bump
    if: needs.bump.outputs.bumped == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: v${{ needs.bump.outputs.version }}
          fetch-depth: 0

      - name: Extract changelog section
        id: section
        run: |
          VERSION="${{ needs.bump.outputs.version }}"
          awk -v v="$VERSION" '
            BEGIN { printing=0 }
            $0 ~ "^## \\[" v "\\]" { printing=1; next }
            printing && /^## \[/ { exit }
            printing { print }
          ' CHANGELOG.md > release_body.md

      - name: Create release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v${{ needs.bump.outputs.version }}
          name: v${{ needs.bump.outputs.version }}
          body_path: release_body.md

  pypi:
    name: Publish to PyPI
    needs: [bump, github_release]
    if: needs.bump.outputs.bumped == 'true'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        package: [plex_audit, plex_audit_cli]
    steps:
      - uses: actions/checkout@v4
        with:
          ref: v${{ needs.bump.outputs.version }}

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Build sdist and wheel
        working-directory: packages/${{ matrix.package }}
        run: uv build

      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: packages/${{ matrix.package }}/dist

  binaries:
    name: Build binary (${{ matrix.os }})
    needs: [bump, github_release]
    if: needs.bump.outputs.bumped == 'true'
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-latest
            asset_name: plex-audit-linux-x64
          - os: macos-latest
            asset_name: plex-audit-macos-arm64
          - os: macos-13
            asset_name: plex-audit-macos-x64
          - os: windows-latest
            asset_name: plex-audit-windows-x64.exe
    steps:
      - uses: actions/checkout@v4
        with:
          ref: v${{ needs.bump.outputs.version }}

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install 3.12

      - name: Install workspace and PyInstaller
        run: |
          uv sync --all-packages
          uv pip install pyinstaller

      - name: Build binary
        shell: bash
        run: |
          uv run pyinstaller --onefile --name "${{ matrix.asset_name }}" \
            --collect-all plex_audit \
            --collect-all plex_audit_cli \
            packages/plex_audit_cli/src/plex_audit_cli/main.py

      - name: Upload to release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v${{ needs.bump.outputs.version }}
          files: dist/${{ matrix.asset_name }}*

  docker:
    name: Build and push Docker image
    needs: [bump, github_release]
    if: needs.bump.outputs.bumped == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: v${{ needs.bump.outputs.version }}

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: docker/Dockerfile
          platforms: linux/amd64,linux/arm64
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/plex_auditor:${{ needs.bump.outputs.version }}
            ghcr.io/${{ github.repository_owner }}/plex_auditor:latest
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow (PyPI, binaries, Docker)"
```

---

## Task 5: Dispatch release from auto-merge

**Files:**
- Modify: `.github/workflows/auto-merge.yml`

After the auto-merge succeeds, trigger `release.yml` via `gh workflow run`. The existing workflow has `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` already.

- [ ] **Step 1: Patch the workflow**

Read `.github/workflows/auto-merge.yml`. Append a new step to the `auto-merge` job, after the `Create PR and merge` step:

```yaml
      - name: Dispatch release workflow
        if: steps.divergence.outputs.ahead != '0'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: gh workflow run release.yml --ref main
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/auto-merge.yml
git commit -m "ci: dispatch release workflow after auto-merge"
```

---

## Task 6: README install/use section

**Files:**
- Modify: `README.md`

Replace the existing "Quick start" section with three install options — pip, binary, Docker — plus a short "First-run" block showing `plex-audit init` → `plex-audit scan`.

- [ ] **Step 1: Replace the quickstart**

Read current `README.md`, then replace the section between `## Quick start` and the next `##` heading with:

````markdown
## Install

Pick one:

**pip** (from PyPI)
```bash
pip install plex-audit
```

**Standalone binary** — grab the right build for your OS from the latest [GitHub Release](https://github.com/LightWraith8268/plex_auditor/releases):
- `plex-audit-linux-x64`
- `plex-audit-macos-arm64` / `plex-audit-macos-x64`
- `plex-audit-windows-x64.exe`

Put it on your `PATH`.

**Docker**
```bash
docker pull ghcr.io/lightwraith8268/plex_auditor:latest
docker run --rm -v $(pwd):/config ghcr.io/lightwraith8268/plex_auditor:latest --help
```

## First run

```bash
plex-audit init                     # interactive wizard → writes config.yaml
plex-audit scan --config config.yaml
plex-audit schedule --show          # prints cron / schtasks snippet
```
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add install and first-run sections to README"
```

---

## Self-review notes

- Every task has either a failing test + code + commit, or a concrete file + commit.
- `bump_version.py` and `update_changelog.py` both ship with pytest coverage; the CI YAML and Dockerfile are reviewed by the fact that the release workflow itself exercises them end-to-end on its first real run.
- Manual prerequisites (PyPI Trusted Publishing setup) are called out at the top of the plan and cannot be automated from within this repo.
- `release.yml` is gated on `bumped == 'true'` so commits like `docs:` or `chore:` don't mint empty releases.
- The `[skip ci]` marker on the release commit prevents an infinite trigger loop (release commit → ci → release commit → ...).
