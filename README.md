# plex_auditor

A public library auditor for Plex Media Server. Scans your Plex libraries and the underlying filesystem to surface problems that the owner should fix: missing content, metadata issues, file-health concerns, and duplicates.

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

Exit codes:
- `0` — clean
- `1` — warnings
- `2` — errors
- `3` — Plex unreachable
- `4` — config invalid

## Built-in checks

| ID | Category | What it flags |
|---|---|---|
| `missing_episodes` | missing | Episode-number gaps within a downloaded season |
| `unmatched_items` | metadata | Items Plex couldn't match to any agent |
| `missing_artwork` | metadata | Items missing a poster or summary |
| `match_confidence` | metadata | Filename year disagrees with Plex metadata |
| `orphaned_files` | file_health | Video files on disk that Plex doesn't know about |
| `missing_files` | file_health | Files Plex references but that aren't on disk |
| `quality_threshold` | file_health | Resolution / bitrate / codec below configured threshold |
| `ffprobe_integrity` | file_health | Files ffprobe rejects (opt-in; needs ffprobe) |
| `duplicates` | duplicate | Same item with multiple file variants |
| `near_duplicates` | duplicate | Different items sharing a normalized title (remakes, editions) |

## Architecture

- `packages/plex_audit` — core library (Plex client, config, path mapper, engine, reporters, built-in checks).
- `packages/plex_audit_cli` — Typer-based CLI wrapper.
- Checks are Python entry-point plugins under the `plex_audit.checks` group, so third-party packages can add checks without forking.

Design spec: `docs/superpowers/specs/2026-04-12-plex-library-auditor-design.md`.

## Development

```bash
git clone https://github.com/LightWraith8268/plex_auditor.git
cd plex_auditor
uv sync --all-packages
uv run pytest -v
uv run ruff check .
uv run mypy packages/plex_audit/src packages/plex_audit_cli/src
```

## Branches and releases

- `main` — default; receives changes only via auto-merged PRs from `claude/dev`.
- `claude/dev` — active development.
- Releases are cut automatically from conventional commits (`feat:` → minor, `fix:`/`perf:` → patch, `feat!:` or `BREAKING CHANGE:` → major).

## License

TBD.
