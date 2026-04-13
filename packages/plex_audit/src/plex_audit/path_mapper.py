from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath, PureWindowsPath


@dataclass(frozen=True)
class PathMapping:
    plex: str
    local: str


def _detect_path_flavor(path: str) -> type[PurePath]:
    # Heuristic: a drive letter or backslash → Windows, else POSIX.
    if len(path) >= 2 and path[1] == ":":
        return PureWindowsPath
    if "\\" in path:
        return PureWindowsPath
    return PurePosixPath


def _normalize_plex_prefix(prefix: str) -> str:
    # Plex paths are POSIX-style. Strip trailing slashes for comparison.
    return prefix.rstrip("/")


class PathMapper:
    def __init__(self, mappings: list[PathMapping]) -> None:
        # Sort longest-prefix first so nested mappings match correctly.
        self._mappings = sorted(
            mappings,
            key=lambda mapping: len(_normalize_plex_prefix(mapping.plex)),
            reverse=True,
        )

    @property
    def has_mappings(self) -> bool:
        return bool(self._mappings)

    def to_local(self, plex_path: str) -> PurePath | None:
        normalized_source = plex_path.rstrip("/")
        for mapping in self._mappings:
            plex_prefix = _normalize_plex_prefix(mapping.plex)
            if normalized_source == plex_prefix or normalized_source.startswith(plex_prefix + "/"):
                remainder = normalized_source[len(plex_prefix) :].lstrip("/")
                flavor = _detect_path_flavor(mapping.local)
                local_root = mapping.local.rstrip("/\\")
                if not remainder:
                    return flavor(local_root)
                return flavor(local_root) / remainder
        return None
