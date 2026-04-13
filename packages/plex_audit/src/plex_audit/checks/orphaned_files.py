from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

VIDEO_EXTENSIONS = frozenset({
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm", ".mpg", ".mpeg", ".ts"
})


class OrphanedFilesCheck:
    id = "orphaned_files"
    name = "Orphaned Files"
    category = Category.FILE_HEALTH
    parallel_safe = True
    requires_filesystem = True

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        if not ctx.path_mapper.has_mappings:
            return

        known_local_files: set[Path] = set()
        local_roots: set[Path] = set()

        for library in ctx.plex.iter_libraries():
            for item in library.raw.all():
                for media_file in ctx.plex.get_media_files(item):
                    local = ctx.path_mapper.to_local(media_file.plex_path)
                    if local is not None:
                        known_local_files.add(Path(str(local)))
                    else:
                        # Plex path may already be a local absolute path (e.g. on
                        # Windows where PathMapper expects POSIX-style separators
                        # but the path contains backslashes). Add it directly so
                        # the known-file set stays accurate.
                        plex_as_path = Path(media_file.plex_path)
                        if plex_as_path.is_absolute():
                            known_local_files.add(plex_as_path)

        for mapping in ctx.config.paths.mappings:
            local_root = Path(mapping.local)
            if local_root.exists():
                local_roots.add(local_root)

        for root in local_roots:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                if path in known_local_files:
                    continue
                finding = Finding(
                    check_id=self.id,
                    severity=Severity.WARN,
                    title="Orphaned file on disk",
                    subject=str(path),
                    file_path=path,
                    suggested_action="Add to a Plex library or delete",
                )
                ctx.report(finding)
                yield finding
