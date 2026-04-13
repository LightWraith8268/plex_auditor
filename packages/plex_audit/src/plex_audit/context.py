from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from plex_audit.types import Finding, Severity

if TYPE_CHECKING:
    from plex_audit.config import Config
    from plex_audit.path_mapper import PathMapper
    from plex_audit.plex_client import PlexClient


class FindingsSink:
    def __init__(self) -> None:
        self._seen: set[Finding] = set()
        self._ordered: list[Finding] = []
        self._lock = threading.Lock()

    def add(self, finding: Finding) -> None:
        with self._lock:
            if finding in self._seen:
                return
            self._seen.add(finding)
            self._ordered.append(finding)

    def all(self) -> list[Finding]:
        with self._lock:
            return sorted(
                self._ordered,
                key=lambda f: (-int(f.severity), f.check_id, f.subject),
            )

    def highest_severity(self) -> Severity | None:
        with self._lock:
            if not self._ordered:
                return None
            return max(f.severity for f in self._ordered)


@dataclass(frozen=True)
class ScanContext:
    plex: PlexClient
    path_mapper: PathMapper
    config: Config
    filesystem_available: bool
    _sink: FindingsSink = field(default_factory=FindingsSink)

    def report(self, finding: Finding) -> None:
        self._sink.add(finding)
