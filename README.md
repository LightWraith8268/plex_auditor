# plex_auditor

A public library auditor for Plex Media Server. Scans your Plex libraries and the underlying filesystem to surface problems that the owner should fix: missing content, metadata issues, file-health concerns, and duplicates.

**Status:** Plan 1 foundation complete — working `plex-audit scan` CLI with the `orphaned_files` check. Additional checks, reporters, and distribution (PyPI + binaries + Docker) arrive in upcoming plans.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/LightWraith8268/plex_auditor.git
cd plex_auditor
uv sync --all-packages

# Edit a config.yaml (see docs/superpowers/specs for the full schema)
uv run plex-audit scan --config config.yaml
```

Exit codes:
- `0` — clean
- `1` — warnings
- `2` — errors
- `3` — Plex unreachable
- `4` — config invalid

## Architecture

- `packages/plex_audit` — core library (Plex client, config, path mapper, engine, reporters, built-in checks)
- `packages/plex_audit_cli` — Typer-based CLI wrapper
- Checks are Python entry-point plugins in the `plex_audit.checks` group; third-party plugins compose without forking.

Design spec: `docs/superpowers/specs/2026-04-12-plex-library-auditor-design.md`.

## Development

```bash
uv sync --all-packages
uv run pytest -v
uv run ruff check .
uv run mypy packages/plex_audit/src packages/plex_audit_cli/src
```

## Branches

- `main` — default; receives changes only via auto-merged PRs from `claude/dev`.
- `claude/dev` — active development.

## License

TBD.
