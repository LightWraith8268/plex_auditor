from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import PurePosixPath

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

_YEAR_REGEX = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


def extract_year_from_path(path: str) -> int | None:
    name = PurePosixPath(path).name
    parent = PurePosixPath(path).parent.name
    for candidate in (name, parent):
        match = _YEAR_REGEX.search(candidate)
        if match:
            return int(match.group(0))
    return None


class MatchConfidenceCheck:
    id = "match_confidence"
    name = "Match Confidence"
    category = Category.METADATA
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        for library in ctx.plex.iter_libraries():
            if library.kind != "movie":
                continue
            for movie in library.raw.all():
                plex_year = getattr(movie, "year", None)
                if plex_year is None:
                    continue
                for media_file in ctx.plex.get_media_files(movie):
                    file_year = extract_year_from_path(media_file.plex_path)
                    if file_year is None:
                        continue
                    if abs(file_year - plex_year) <= 1:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.WARN,
                        title="Year in filename disagrees with Plex metadata",
                        subject=str(movie.title),
                        details={"filename_year": file_year, "plex_year": plex_year},
                        plex_item_id=str(movie.ratingKey),
                        suggested_action="Verify the match and re-match if incorrect.",
                    )
                    ctx.report(finding)
                    yield finding
                    break  # one finding per movie max
