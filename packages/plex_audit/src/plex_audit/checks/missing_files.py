from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class MissingFilesCheck:
    id = "missing_files"
    name = "Files Missing on Disk"
    category = Category.FILE_HEALTH
    parallel_safe = True
    requires_filesystem = True

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            for item in library.raw.all():
                for media_file in ctx.plex.get_media_files(item):
                    local = ctx.path_mapper.to_local(media_file.plex_path)
                    if local is None:
                        continue
                    local_path = Path(str(local))
                    if local_path.exists():
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.ERROR,
                        title="File referenced by Plex is missing on disk",
                        subject=media_file.plex_path,
                        details={"library": library.title, "rating_key": media_file.rating_key},
                        plex_item_id=media_file.rating_key,
                        file_path=local_path,
                        suggested_action="Restore the file or remove the entry from Plex.",
                    )
                    ctx.report(finding)
                    yield finding
