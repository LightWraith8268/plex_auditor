from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from plex_audit.types import Finding, Severity


class MarkdownReporter:
    format = "md"

    def write(self, findings: list[Finding], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        lines.append("# Plex Audit Report")
        lines.append("")
        lines.append(f"_Generated {datetime.now(UTC).isoformat(timespec='seconds')}_")
        lines.append("")
        lines.append(f"**Total findings:** {len(findings)}")
        lines.append("")

        if not findings:
            lines.append("No findings. Library looks clean.")
            output_path.write_text("\n".join(lines), encoding="utf-8")
            return

        by_severity: dict[Severity, list[Finding]] = defaultdict(list)
        for f in findings:
            by_severity[f.severity].append(f)

        for severity in (Severity.ERROR, Severity.WARN, Severity.INFO):
            bucket = by_severity.get(severity, [])
            if not bucket:
                continue
            lines.append(f"## {severity.name} ({len(bucket)})")
            lines.append("")
            for f in bucket:
                lines.append(f"### [{f.check_id}] {f.title} — {f.subject}")
                if f.file_path is not None:
                    lines.append(f"- **File:** `{f.file_path}`")
                if f.plex_item_id:
                    lines.append(f"- **Plex item:** `{f.plex_item_id}`")
                if f.suggested_action:
                    lines.append(f"- **Suggested action:** {f.suggested_action}")
                if f.details:
                    lines.append("- **Details:**")
                    for key, value in sorted(f.details.items()):
                        lines.append(f"  - `{key}`: {value}")
                lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")
