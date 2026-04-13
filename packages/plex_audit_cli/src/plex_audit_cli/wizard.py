from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from plex_audit.config import PlexConfig
from plex_audit.plex_client import PlexClient

TOKEN_HELP_URL = "https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/"


def run_wizard(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config.yaml"),
) -> None:
    """Interactively build config.yaml."""
    typer.echo("plex-audit init — this will create a config.yaml for your Plex server.\n")

    url = typer.prompt("Plex URL", default="http://localhost:32400")
    typer.echo(f"(Need your token? See {TOKEN_HELP_URL})")
    token = typer.prompt("Plex token", hide_input=True)

    client = PlexClient(PlexConfig(url=url, token=token))
    try:
        libraries = list(client.iter_libraries())
    except Exception as exc:
        typer.secho(f"Could not reach Plex: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.echo(f"\nFound {len(libraries)} libraries:")
    for lib in libraries:
        typer.echo(f"  - [{lib.kind}] {lib.title}")
    typer.echo()

    mappings: list[dict[str, str]] = []
    for lib in libraries:
        remote_paths = list(getattr(lib.raw, "locations", None) or [])
        for remote_path in remote_paths:
            local = typer.prompt(
                f"Local path for Plex library '{lib.title}' (Plex sees {remote_path}, or blank to skip)",
                default="",
                show_default=False,
            )
            if local.strip():
                mappings.append({"plex": remote_path, "local": local.strip()})

    formats_raw = typer.prompt("Report formats (comma-separated from md,json,html)", default="md")
    formats = [f.strip() for f in formats_raw.split(",") if f.strip()]

    output_dir = typer.prompt("Output directory for reports", default="./reports")

    config = {
        "plex": {"url": url, "token": token, "verify_ssl": True, "timeout_seconds": 30},
        "paths": {"mappings": mappings},
        "checks": {"enabled": "all", "disabled": [], "config": {}},
        "report": {
            "formats": formats,
            "output_dir": output_dir,
            "filename_template": "plex-audit-{timestamp}",
        },
        "logging": {"level": "INFO", "file": "./plex-audit.log"},
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    typer.secho(f"\nWrote {config_path}", fg=typer.colors.GREEN)
    typer.echo(f"Run `plex-audit scan --config {config_path}` to audit.")
    typer.echo(f"Run `plex-audit schedule --show --config {config_path}` for a cron/scheduled-task template.")
