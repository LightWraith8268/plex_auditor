from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class UnmatchedItemsCheck:
    id = "unmatched_items"
    name = "Unmatched Items"
    category = Category.METADATA
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind not in ("movie", "show"):
                continue
            for item in library.raw.all():
                guid = getattr(item, "guid", None)
                if guid and not str(guid).startswith("local://"):
                    continue
                finding = Finding(
                    check_id=self.id,
                    severity=Severity.WARN,
                    title="Item not matched to any agent",
                    subject=str(item.title),
                    details={"library": library.title, "kind": library.kind},
                    plex_item_id=str(item.ratingKey),
                    suggested_action="Use Plex 'Match…' to pick the correct metadata entry.",
                )
                ctx.report(finding)
                yield finding
