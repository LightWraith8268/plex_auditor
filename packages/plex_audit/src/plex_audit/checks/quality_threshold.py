from __future__ import annotations

from collections.abc import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

_RESOLUTION_ORDER = {"sd": 0, "480": 480, "576": 576, "720": 720, "1080": 1080, "1440": 1440, "2160": 2160, "4k": 2160}


def _resolution_as_int(value: object) -> int:
    if value is None:
        return 0
    s = str(value).lower().strip("p ")
    if s in _RESOLUTION_ORDER:
        return _RESOLUTION_ORDER[s]
    try:
        return int(s)
    except ValueError:
        return 0


class QualityThresholdCheck:
    id = "quality_threshold"
    name = "Quality Threshold"
    category = Category.FILE_HEALTH
    parallel_safe = True
    requires_filesystem = False

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        cfg = ctx.config.checks.config.get(self.id, {})
        min_res = _resolution_as_int(cfg.get("min_resolution", "1080"))
        min_bitrate = int(cfg.get("min_bitrate_kbps", 2000))
        allowed_codecs = {c.lower() for c in cfg.get("allowed_codecs", ["h264", "hevc", "av1"])}

        for library in ctx.plex.iter_libraries():
            if library.kind not in ("movie", "show"):
                continue
            for item in self._iter_playable(library):
                for media in getattr(item, "media", []) or []:
                    issues = {}
                    if _resolution_as_int(getattr(media, "videoResolution", None)) < min_res:
                        issues["resolution"] = getattr(media, "videoResolution", None)
                    if int(getattr(media, "bitrate", 0) or 0) < min_bitrate:
                        issues["bitrate_kbps"] = getattr(media, "bitrate", 0)
                    codec = str(getattr(media, "videoCodec", "")).lower()
                    if codec and codec not in allowed_codecs:
                        issues["codec"] = codec
                    if not issues:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.WARN,
                        title="Below quality threshold",
                        subject=str(getattr(item, "title", getattr(item, "grandparentTitle", "unknown"))),
                        details=issues,
                        plex_item_id=str(getattr(item, "ratingKey", "")),
                        suggested_action="Consider upgrading the source.",
                    )
                    ctx.report(finding)
                    yield finding

    def _iter_playable(self, library):
        if library.kind == "movie":
            yield from library.raw.all()
        else:
            for show in library.raw.all():
                for season in show.seasons():
                    yield from season.episodes()
