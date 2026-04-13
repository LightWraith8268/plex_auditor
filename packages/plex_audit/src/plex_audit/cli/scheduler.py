from __future__ import annotations

import platform
from pathlib import Path
from typing import Annotated

import typer

SUPPORTED_OS = ("linux", "macos", "windows")
EXECUTABLE_NAME = "plex-audit"


def show_schedule(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config.yaml"),
    show: Annotated[bool, typer.Option("--show", help="Print the schedule snippet.")] = False,
    target_os: Annotated[str | None, typer.Option("--os", help="Override detected OS (linux, macos, windows).")] = None,
) -> None:
    """Emit a scheduled-task snippet for your OS."""
    if not show:
        typer.secho("Pass --show to print the snippet.", err=True, fg=typer.colors.YELLOW)
        raise typer.Exit(code=2)

    detected = (target_os or _detect_os()).lower()
    if detected not in SUPPORTED_OS:
        typer.secho(f"Unsupported OS: {detected}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)

    if detected in ("linux", "macos"):
        typer.echo("# Add this to your crontab (runs daily at 03:00):")
        typer.echo(f"0 3 * * * {EXECUTABLE_NAME} scan --config {config_path}")
    else:
        typer.echo("REM Run daily at 03:00. Adjust /TN as desired.")
        typer.echo(
            f'schtasks /Create /SC DAILY /TN "PlexAudit" /TR '
            f'"\\"{EXECUTABLE_NAME}\\" scan --config \\"{config_path}\\"" /ST 03:00 /F'
        )


def _detect_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system
