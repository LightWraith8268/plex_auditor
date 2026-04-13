from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path

from plex_audit.context import ScanContext
from plex_audit.plex_client import Library
from plex_audit.types import Category, Finding, Severity


class FfprobeIntegrityCheck:
    id = "ffprobe_integrity"
    name = "FFprobe Integrity"
    category = Category.FILE_HEALTH
    parallel_safe = False
    requires_filesystem = True

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        cfg = ctx.config.checks.config.get(self.id, {})
        if not cfg.get("enabled", False):
            return

        ffprobe_path = shutil.which("ffprobe")
        if ffprobe_path is None:
            finding = Finding(
                check_id=self.id,
                severity=Severity.ERROR,
                title="ffprobe binary not found; integrity check disabled",
                subject="ffprobe_integrity",
                suggested_action="Install ffmpeg/ffprobe or disable this check.",
            )
            ctx.report(finding)
            yield finding
            return

        for library in ctx.plex.iter_libraries():
            for item in self._iter_playable(library):
                for media_file in ctx.plex.get_media_files(item):
                    local = ctx.path_mapper.to_local(media_file.plex_path)
                    if local is None:
                        continue
                    local_path = Path(str(local))
                    if not local_path.exists():
                        continue
                    result = subprocess.run(
                        [ffprobe_path, "-v", "error", "-of", "json", str(local_path)],
                        capture_output=True, text=True, check=False,
                    )
                    if result.returncode == 0:
                        continue
                    finding = Finding(
                        check_id=self.id,
                        severity=Severity.ERROR,
                        title="ffprobe reported errors reading file",
                        subject=str(local_path),
                        details={"stderr": (result.stderr or "").strip()[:500]},
                        plex_item_id=media_file.rating_key,
                        file_path=local_path,
                        suggested_action="Inspect the file; consider re-sourcing.",
                    )
                    ctx.report(finding)
                    yield finding

    def _iter_playable(self, library: Library) -> Iterable[object]:
        if library.kind == "movie":
            yield from library.raw.all()
        elif library.kind == "show":
            for show in library.raw.all():
                for season in show.seasons():
                    yield from season.episodes()
