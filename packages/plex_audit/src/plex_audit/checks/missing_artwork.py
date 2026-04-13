from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class MissingArtworkCheck:
    id = "missing_artwork"
    name = "Missing Artwork or Summary"
    category = Category.METADATA
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind not in ("movie", "show"):
                continue
            for item in library.raw.all():
                if not getattr(item, "thumb", None):
                    finding = self._finding(item, library.title, "poster")
                    ctx.report(finding)
                    yield finding
                if not (getattr(item, "summary", "") or "").strip():
                    finding = self._finding(item, library.title, "summary")
                    ctx.report(finding)
                    yield finding

    def _finding(self, item: object, library: str, issue: str) -> Finding:
        return Finding(
            check_id=self.id,
            severity=Severity.INFO,
            title=f"Missing {issue}",
            subject=str(getattr(item, "title", "unknown")),
            details={"library": library, "issue": issue},
            plex_item_id=str(getattr(item, "ratingKey", "")),
            suggested_action=f"Add a {issue} in Plex or refresh metadata.",
        )
