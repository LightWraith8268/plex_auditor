from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import entry_points
from typing import Literal

from plex_audit.context import ScanContext
from plex_audit.types import Check, Finding, Severity

log = logging.getLogger(__name__)


class Engine:
    ENTRY_POINT_GROUP = "plex_audit.checks"

    def __init__(self, checks: list[Check]) -> None:
        self._checks = checks

    @classmethod
    def from_entry_points(cls) -> Engine:
        discovered: list[Check] = []
        for entry in entry_points(group=cls.ENTRY_POINT_GROUP):
            try:
                check_cls = entry.load()
                discovered.append(check_cls())
            except Exception as exc:  # pragma: no cover — defensive
                log.warning("Failed to load check %s: %s", entry.name, exc)
        return cls(discovered)

    def _select(
        self,
        enabled: Literal["all"] | list[str],
        disabled: list[str],
    ) -> list[Check]:
        if enabled == "all":
            selected = list(self._checks)
        else:
            selected = [c for c in self._checks if c.id in enabled]
        return [c for c in selected if c.id not in disabled]

    def run(
        self,
        ctx: ScanContext,
        enabled: Literal["all"] | list[str],
        disabled: list[str],
    ) -> None:
        to_run: list[Check] = []
        for check in self._select(enabled, disabled):
            if check.requires_filesystem and not ctx.filesystem_available:
                ctx.report(
                    Finding(
                        check_id="engine",
                        severity=Severity.INFO,
                        title="Check skipped: filesystem unavailable",
                        subject=check.id,
                    )
                )
                continue
            to_run.append(check)

        parallel = [c for c in to_run if c.parallel_safe]
        serial = [c for c in to_run if not c.parallel_safe]

        if parallel:
            with ThreadPoolExecutor(max_workers=max(1, len(parallel))) as pool:
                list(pool.map(lambda c: self._run_one(c, ctx), parallel))
        for c in serial:
            self._run_one(c, ctx)

    def _run_one(self, check: Check, ctx: ScanContext) -> None:
        try:
            for finding in check.run(ctx):
                ctx.report(finding)
        except Exception as exc:
            log.exception("Check %s crashed", check.id)
            ctx.report(
                Finding(
                    check_id="engine",
                    severity=Severity.ERROR,
                    title=f"Check crashed: {exc.__class__.__name__}",
                    subject=check.id,
                    details={"traceback": traceback.format_exc()},
                )
            )
