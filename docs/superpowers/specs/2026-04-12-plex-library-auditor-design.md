# Plex Library Auditor — Design

**Date:** 2026-04-12
**Status:** Approved (brainstorming phase)
**Owner:** padra

## Purpose

A public, open-source tool that audits a Plex Media Server library and reports problems the owner should fix. It detects missing content, metadata issues, file-health problems, and duplicates. Designed to be run on demand or on a schedule, and to be distributed broadly (pip, standalone binary, Docker).

## Goals

- Produce actionable audit reports for Plex libraries.
- Work against any Plex setup: local, remote, or co-located on the Plex host.
- Distribute as a public tool: pip package, platform binaries, Docker image.
- Support future extensions (notably Sonarr/Radarr integration) without core changes.
- Run as a one-shot CLI; scheduling is delegated to the OS (cron / Task Scheduler).

## Non-goals (v1)

- No daemon or always-on web UI.
- No auto-remediation — the auditor reports; the user decides.
- No direct Sonarr/Radarr integration in v1; architecture supports it as a later plugin.
- No TVDB/TMDB integration for "missing latest episodes" — that capability ships with the *arrs plugin.

## Users

Public Plex server operators running Windows, macOS, Linux, or Docker/NAS. Skill levels vary from casual (wants a binary + wizard) to power-user (wants pip + YAML + plugins).

## Deployment Topologies

The tool must work in all three:

1. Plex and auditor on the same Windows/macOS/Linux host (local paths match directly).
2. Plex on a remote host (NAS/Linux server); auditor runs on a workstation against the Plex HTTP API and a mounted network share.
3. Auditor runs on the Plex host itself (often via Docker).

Path mapping is first-class configuration because (2) requires translating Plex-reported paths to paths the auditor can see.

## Checks (v1 catalog)

**Missing content**
1. Incomplete TV seasons (episode number gaps within a downloaded season)
2. Incomplete collections (movies tagged as part of a collection but collection is incomplete)

**Metadata**
3. Unmatched items (Plex could not match to any agent)
4. Missing posters / artwork / summary
5. Low match confidence / possible mismatches (e.g., year mismatch between filename and Plex metadata)

**File health**
6. Orphaned files on disk not represented in any Plex library
7. Files referenced by Plex but missing on disk
8. Below-threshold quality (configurable: resolution, bitrate, codec)
9. Unplayable / corrupt files via `ffprobe` (opt-in, slow)

**Duplicates**
10. Same item with multiple file versions
11. Near-duplicates (same title, different editions/years)

**Deferred (ships with *arrs plugin)**
- Missing latest episodes (aired but not downloaded) — requires Sonarr as source of truth.
- Missing movies in a watchlist/library request — requires Radarr.

## Architecture

**Option chosen: Core library + CLI wrapper + plugin-based checks.**

Two packages in one monorepo. The core library knows nothing about the CLI. Checks are registered via Python entry points, so third-party or future official plugins (Sonarr/Radarr, custom checks, web UI) compose cleanly.

### Repository layout

```
plex_tools/
├── packages/
│   ├── plex_audit/              # core library
│   │   └── src/plex_audit/
│   │       ├── plex_client.py        # wraps python-plexapi, caches per-scan
│   │       ├── path_mapper.py        # Plex-path → local-path translation
│   │       ├── config.py             # pydantic models + loader
│   │       ├── engine.py             # plugin discovery + execution
│   │       ├── checks/
│   │       │   ├── base.py           # Check protocol, Finding dataclass
│   │       │   ├── missing_episodes.py
│   │       │   ├── incomplete_collections.py
│   │       │   ├── unmatched_items.py
│   │       │   ├── missing_artwork.py
│   │       │   ├── match_confidence.py
│   │       │   ├── orphaned_files.py
│   │       │   ├── missing_files.py
│   │       │   ├── quality_threshold.py
│   │       │   ├── ffprobe_integrity.py
│   │       │   ├── duplicates.py
│   │       │   └── near_duplicates.py
│   │       ├── reporters/
│   │       │   ├── markdown.py
│   │       │   ├── json.py
│   │       │   └── html.py
│   │       └── api.py                # public surface for wrappers
│   └── plex_audit_cli/          # CLI wrapper
│       └── src/plex_audit_cli/
│           ├── main.py               # Typer entry point
│           ├── wizard.py             # `plex-audit init`
│           └── scheduler.py          # emits cron / schtasks snippets
├── docker/Dockerfile
├── docs/
├── tests/
├── .github/workflows/             # release → PyPI + binaries + GHCR
└── pyproject.toml
```

### Core components

- **`PlexClient`** — thin wrapper over `python-plexapi`. Connects via URL + token. Exposes typed helpers used by checks (`iter_libraries`, `iter_shows`, `iter_movies`, `iter_episodes`, `get_media_files`). Caches within one scan run.
- **`PathMapper`** — ordered `(plex_prefix → local_prefix)` rules. Returns the local path, or `None` if unmapped (triggers graceful skip for that item). Handles Windows/POSIX path differences.
- **`Config`** — pydantic models. Loads from `config.yaml`. Precedence: CLI flags > `PLEX_AUDIT_*` env vars > `config.yaml` > defaults.
- **`Engine`** — discovers registered checks via `importlib.metadata.entry_points(group="plex_audit.checks")`. Filters by config + CLI flags. Runs `parallel_safe=True` checks concurrently in a `ThreadPoolExecutor`. Catches per-check exceptions and converts to ERROR findings without aborting the scan.
- **`ScanContext`** — immutable bundle passed to each check: `PlexClient`, `PathMapper`, `Config`, `filesystem_available: bool`, `report(finding)` sink.
- **`Reporters`** — one per format. Each takes the final `list[Finding]` and writes one file. User selects via `--format md,json,html`.

### Check plugin interface

```python
class Check(Protocol):
    id: str                     # stable, e.g. "missing_episodes"
    name: str                   # human-readable
    category: Category          # MISSING | METADATA | FILE_HEALTH | DUPLICATE
    parallel_safe: bool = True
    requires_filesystem: bool = False  # engine skips cleanly if no mappings

    def run(self, ctx: ScanContext) -> Iterable[Finding]: ...
```

```python
@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: Severity            # INFO | WARN | ERROR
    title: str
    subject: str                  # e.g., "Breaking Bad"
    details: dict                 # structured, check-specific
    plex_item_id: str | None
    file_path: Path | None
    suggested_action: str | None
```

Built-in checks register in `plex_audit`'s `pyproject.toml`:

```toml
[project.entry-points."plex_audit.checks"]
missing_episodes = "plex_audit.checks.missing_episodes:MissingEpisodesCheck"
orphaned_files = "plex_audit.checks.orphaned_files:OrphanedFilesCheck"
# ...
```

Third-party packages (e.g., future `plex_audit_arrs`) add their own entries; the engine picks them up automatically.

### Data flow — one scan

1. `plex-audit scan` → CLI loads config, constructs `ScanContext`.
2. Engine discovers and filters checks.
3. Engine runs checks (concurrent where safe).
4. Each check yields `Finding`s into a shared `FindingsSink`.
5. Sink deduplicates and sorts (severity → category → subject).
6. Each enabled reporter writes its output file.
7. Process exits with status code (see Error Handling).

## Configuration

### `config.yaml`

```yaml
plex:
  url: http://192.168.1.10:32400
  token: "xxxx"
  verify_ssl: true
  timeout_seconds: 30

paths:
  mappings:
    - plex: /media/tv
      local: \\NAS\media\tv
    - plex: /media/movies
      local: D:\Media\Movies

checks:
  enabled: all            # or explicit list of check IDs
  disabled: []
  config:
    quality_threshold:
      min_resolution: 1080p
      min_bitrate_kbps: 2000
      allowed_codecs: [h264, hevc, av1]
    duplicates:
      ignore_editions: false
    ffprobe_integrity:
      enabled: false

report:
  formats: [md, json, html]
  output_dir: ./reports
  filename_template: "plex-audit-{timestamp}"

logging:
  level: INFO
  file: ./plex-audit.log
```

### `plex-audit init` wizard

1. Prompt for Plex URL + token (with help link for finding the token).
2. Test the connection; echo discovered libraries as confirmation.
3. For each library, display Plex's path and prompt for the local equivalent (or "skip — no filesystem access for this library").
4. Ask which check categories to enable.
5. Ask default report format(s) and output directory.
6. Write `config.yaml`. Offer to print a cron / `schtasks` line for scheduling.

### Scheduling

The tool is never a daemon. `plex-audit schedule --show` prints a ready-to-paste cron line (Linux/macOS) or `schtasks` command (Windows). Users own the scheduler.

## Error Handling

Guiding rule: a partial scan is more useful than no scan.

| Situation | Behavior | Exit code |
|---|---|---|
| Plex unreachable at startup | Fatal, clear remediation hint | 3 |
| Config invalid | Fatal, pydantic errors rendered inline | 4 |
| Individual check crashes | Caught; logged as ERROR finding; scan continues | reflected in 1/2 |
| Per-item failure inside a check | Caught; WARN finding; check continues | reflected in 1 |
| No path mappings / filesystem unavailable | Filesystem-required checks skipped with INFO finding each | not fatal |
| Partial path mapping | Run on mapped libraries; INFO per unmapped library | not fatal |
| Plex API transient error | 3 retries with exponential backoff; then per-item WARN | reflected in 1 |
| `ffprobe` missing when enabled | Check emits one ERROR and self-disables for the run | reflected in 2 |
| Clean scan | — | 0 |
| Scan with warnings only | — | 1 |
| Scan with errors | — | 2 |

Logs (structured, rotated) go to `plex-audit.log`. Findings go into report files — logs and findings are distinct streams.

## Testing Strategy

- **Unit tests** (no network, no disk): `PathMapper`, `Config` precedence, `FindingsSink` dedup/sort, each reporter's output, exit-code mapping.
- **Check tests**: each check runs against a fake `PlexClient` (in-memory fixtures) and a fake filesystem (`tmp_path` / pyfakefs). Each check ships fixtures for: clean library, each failure mode, edge cases (empty library, Unicode paths, very long names).
- **Engine tests**: entry-point discovery (register a fake check in a test package), parallel execution, per-check crash isolation, filesystem-skip behavior.
- **CLI tests**: Typer `CliRunner`. Wizard scripted-input flow, flag-overrides-config, `--format` selection, exit codes.
- **Integration tests** (opt-in, `pytest -m integration`): run against a disposable Plex container with a tiny seeded library. CI runs these on `main`; contributors skip by default.
- **Fixtures**: `tests/fixtures/plex_responses/` holds sanitized captured Plex API JSON that drives the fake client.

Targets: 85% coverage on `plex_audit` core; mypy strict on core; ruff for lint. Enforced in CI.

CI matrix: Python 3.11/3.12/3.13 × Windows/macOS/Linux for unit + check + engine + CLI tests.

## Distribution

Three artifacts, one version, one release pipeline.

1. **PyPI** — `pip install plex-audit` installs `plex_audit` + `plex_audit_cli`. Extras like `plex-audit[arrs]` pull optional plugin packages.
2. **Standalone binaries** — PyInstaller one-file builds for `win-x64`, `macos-arm64`, `macos-x64`, `linux-x64`, `linux-arm64`. Uploaded to GitHub Releases.
3. **Docker image** — `ghcr.io/<user>/plex-audit:<version>` and `:latest`, multi-arch (amd64 + arm64). Entrypoint is the CLI. Config mounted at `/config/config.yaml`, reports at `/reports`. Includes `ffprobe` in the image.

### Release flow

Matches the standard InkNIron Apps pattern:

- Work on `claude/dev`; auto-merge workflow opens PR to `main` and merges with `--admin`.
- On push to `main`, `release.yml` runs: tests → auto-bump version from conventional commits (feat → minor, fix → patch, breaking → major) → tag → GitHub Release with generated changelog → parallel jobs publish PyPI, binaries, and the Docker image.
- Version-bump commits use `[skip ci]`.

### Versioning

SemVer. The check-plugin interface (`Check` protocol, `Finding` dataclass, `ScanContext` shape) is part of the public API — any breaking change there forces a major bump. Protects third-party plugin authors.

## Documentation

- `README.md` with quickstart for pip, binary, and Docker installs.
- `docs/config.md` — full config reference.
- `docs/writing-a-check.md` — plugin authoring guide.
- `docs/arrs-roadmap.md` — planned Sonarr/Radarr integration shape.
- Published via GitHub Pages on release.

## Future Work

- `plex_audit_arrs` plugin package: adds Sonarr/Radarr-powered checks (missing aired episodes, missing requested movies, quality upgrade candidates).
- Optional long-running mode with web dashboard (imports `plex_audit` directly — no core changes needed).
- Findings history / trend tracking (SQLite in the reports dir).
- Notification reporters (email, Discord, webhook) as additional plugin packages.
