from __future__ import annotations

from pathlib import Path
from typing import Protocol

from plex_audit.types import Finding


class Reporter(Protocol):
    format: str

    def write(self, findings: list[Finding], output_path: Path) -> None: ...
