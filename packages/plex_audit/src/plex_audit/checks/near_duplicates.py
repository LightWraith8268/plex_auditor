from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

_EDITION_REGEX = re.compile(
    r"[\(\[][^\)\]]*(cut|edition|extended|remaster|imax|director|theatrical)[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
_YEAR_REGEX = re.compile(r"[\(\[]?\b(19|20)\d{2}\b[\)\]]?")
_PUNCT_REGEX = re.compile(r"[^\w\s]")


def normalize_title(title: str, strip_editions: bool = False) -> str:
    working = title
    if strip_editions:
        working = _EDITION_REGEX.sub("", working)
    working = _YEAR_REGEX.sub("", working)
    working = _PUNCT_REGEX.sub("", working)
    return " ".join(working.lower().split())


class NearDuplicatesCheck:
    id = "near_duplicates"
    name = "Near-Duplicate Titles"
    category = Category.DUPLICATE
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        cfg = ctx.config.checks.config.get(self.id, {})
        strip_editions = bool(cfg.get("ignore_editions", False))

        for library in ctx.plex.iter_libraries():
            if library.kind != "movie":
                continue
            groups: dict[str, list[object]] = defaultdict(list)
            for movie in library.raw.all():
                key = normalize_title(str(movie.title), strip_editions=strip_editions)
                groups[key].append(movie)

            for key, members in groups.items():
                if len(members) < 2:
                    continue
                finding = Finding(
                    check_id=self.id,
                    severity=Severity.INFO,
                    title=f"{len(members)} items share a normalized title",
                    subject=key,
                    details={
                        "items": [
                            {
                                "title": getattr(m, "title", ""),
                                "year": getattr(m, "year", None),
                                "rating_key": str(getattr(m, "ratingKey", "")),
                            }
                            for m in members
                        ],
                        "library": library.title,
                    },
                    suggested_action="Verify these are intentional (e.g., remakes) or merge/remove.",
                )
                ctx.report(finding)
                yield finding
