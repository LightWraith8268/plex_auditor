from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class DuplicatesCheck:
    id = "duplicates"
    name = "Duplicate Media Files"
    category = Category.DUPLICATE
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            for item in self._iter_playable(library):
                files = [mf.plex_path for mf in ctx.plex.get_media_files(item)]
                if len(files) < 2:
                    continue
                finding = Finding(
                    check_id=self.id,
                    severity=Severity.INFO,
                    title=f"{len(files)} file variants for one item",
                    subject=str(getattr(item, "title", getattr(item, "grandparentTitle", "unknown"))),
                    details={"files": files, "library": library.title},
                    plex_item_id=str(getattr(item, "ratingKey", "")),
                    suggested_action="Keep the best quality; delete others if desired.",
                )
                ctx.report(finding)
                yield finding

    def _iter_playable(self, library):
        if library.kind == "movie":
            yield from library.raw.all()
        elif library.kind == "show":
            for show in library.raw.all():
                for season in show.seasons():
                    yield from season.episodes()
