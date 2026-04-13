from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from plex_audit.context import ScanContext


class Severity(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2


class Category(Enum):
    MISSING = "missing"
    METADATA = "metadata"
    FILE_HEALTH = "file_health"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: Severity
    title: str
    subject: str
    details: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)
    plex_item_id: str | None = None
    file_path: Path | None = None
    suggested_action: str | None = None


@runtime_checkable
class Check(Protocol):
    id: str
    name: str
    category: Category
    parallel_safe: bool
    requires_filesystem: bool

    def run(self, ctx: ScanContext) -> Iterable[Finding]: ...
