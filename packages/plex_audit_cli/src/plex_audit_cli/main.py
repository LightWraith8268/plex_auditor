from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from plex_audit.config import Config, ConfigError, load_config
from plex_audit.context import FindingsSink, ScanContext
from plex_audit.engine import Engine
from plex_audit.path_mapper import PathMapper, PathMapping
from plex_audit.plex_client import PlexClient
from plex_audit.reporters.markdown import MarkdownReporter
from plex_audit.types import Severity

app = typer.Typer(help="Plex Media Server library auditor")
log = logging.getLogger("plex_audit_cli")

EXIT_CLEAN = 0
EXIT_WARNINGS = 1
EXIT_ERRORS = 2
EXIT_PLEX_UNREACHABLE = 3
EXIT_CONFIG_INVALID = 4


def _configure_logging(config: Config) -> None:
    Path(config.logging.file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=config.logging.level,
        filename=config.logging.file,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _build_path_mapper(config: Config) -> PathMapper:
    return PathMapper([PathMapping(plex=m.plex, local=m.local) for m in config.paths.mappings])


def _output_path(config: Config, fmt: str) -> Path:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    name = config.report.filename_template.format(timestamp=timestamp)
    return Path(config.report.output_dir) / f"{name}.{fmt}"


def _exit_code_for(highest: Severity | None) -> int:
    if highest is None or highest == Severity.INFO:
        return EXIT_CLEAN
    if highest == Severity.WARN:
        return EXIT_WARNINGS
    return EXIT_ERRORS


@app.command()
def version() -> None:
    """Print the version and exit."""
    import importlib.metadata

    typer.echo(importlib.metadata.version("plex-audit-cli"))


@app.command()
def scan(
    config_path: Annotated[Path, typer.Option("--config", "-c", help="Path to config.yaml")] = Path("config.yaml"),
) -> None:
    """Run a full audit and write reports."""
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.secho(f"Config error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=EXIT_CONFIG_INVALID) from exc

    _configure_logging(config)

    path_mapper = _build_path_mapper(config)
    plex_client = PlexClient(config.plex)

    try:
        list(plex_client.iter_libraries())
    except Exception as exc:
        typer.secho(f"Could not reach Plex: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=EXIT_PLEX_UNREACHABLE) from exc

    sink = FindingsSink()
    ctx = ScanContext(
        plex=plex_client,
        path_mapper=path_mapper,
        config=config,
        filesystem_available=path_mapper.has_mappings,
        _sink=sink,
    )

    engine = Engine.from_entry_points()
    engine.run(ctx, enabled=config.checks.enabled, disabled=config.checks.disabled)

    all_findings = sink.all()
    # Exclude engine-internal skip notices (check_id="engine", severity=INFO)
    # from user-facing reports; they are operational metadata, not audit findings.
    report_findings = [
        finding
        for finding in all_findings
        if not (finding.check_id == "engine" and finding.severity == Severity.INFO)
    ]
    for fmt in config.report.formats:
        if fmt == "md":
            MarkdownReporter().write(report_findings, _output_path(config, "md"))

    typer.echo(f"Scan complete. {len(report_findings)} finding(s).")
    raise typer.Exit(code=_exit_code_for(sink.highest_severity()))


if __name__ == "__main__":
    app()
