from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity


class MissingEpisodesCheck:
    id = "missing_episodes"
    name = "Missing Episodes"
    category = Category.MISSING
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind != "show":
                continue
            for show in library.raw.all():
                for season in show.seasons():
                    indexes = sorted({ep.index for ep in season.episodes()})
                    if len(indexes) < 2:
                        continue
                    expected = set(range(indexes[0], indexes[-1] + 1))
                    missing = sorted(expected - set(indexes))
                    if not missing:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.WARN,
                        title=f"Season {season.index} missing {len(missing)} episode(s)",
                        subject=f"{show.title} — Season {season.index}",
                        details={"season": season.index, "missing": missing, "show": show.title},
                        plex_item_id=str(show.ratingKey),
                        suggested_action="Check Sonarr/download client for missing episodes.",
                    )
                    ctx.report(finding)
                    yield finding
