from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from plex_audit.types import Finding


class JsonReporter:
    format = "json"

    def write(self, findings: list[Finding], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "total": len(findings),
            "findings": [self._serialize(f) for f in findings],
        }
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    def _serialize(self, finding: Finding) -> dict[str, Any]:
        raw = asdict(finding)
        raw["severity"] = finding.severity.name
        if finding.file_path is not None:
            raw["file_path"] = finding.file_path.as_posix()
        for key in ("file_path", "plex_item_id", "suggested_action"):
            if raw.get(key) is None:
                raw.pop(key, None)
        return raw
