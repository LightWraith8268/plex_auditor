from __future__ import annotations

import html
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from plex_audit.types import Finding, Severity

_STYLES = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #222; }
h1 { margin-bottom: 0.25rem; }
.meta { color: #666; margin-bottom: 1.5rem; }
h2 { margin-top: 2.5rem; border-bottom: 2px solid currentColor; padding-bottom: 0.25rem; }
h2.sev-error { color: #b91c1c; }
h2.sev-warn  { color: #b45309; }
h2.sev-info  { color: #1d4ed8; }
table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; }
th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
th { background: #f9fafb; cursor: pointer; user-select: none; font-weight: 600; }
th:hover { background: #f3f4f6; }
code { background: #f3f4f6; padding: 0.1rem 0.35rem; border-radius: 3px; font-size: 0.92em; }
.clean { padding: 2rem; background: #ecfdf5; color: #065f46; border-radius: 6px; text-align: center; font-size: 1.1rem; }
""".strip()

_SORT_SCRIPT = """
document.querySelectorAll('table').forEach(function(table) {
  table.querySelectorAll('th').forEach(function(th, col) {
    th.addEventListener('click', function() {
      var tbody = table.tBodies[0];
      var rows = Array.from(tbody.rows);
      var asc = !th.dataset.asc || th.dataset.asc === 'false';
      rows.sort(function(a, b) {
        var av = a.cells[col].innerText.toLowerCase();
        var bv = b.cells[col].innerText.toLowerCase();
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(function(r) { tbody.appendChild(r); });
      th.dataset.asc = asc ? 'true' : 'false';
    });
  });
});
""".strip()


class HtmlReporter:
    format = "html"

    def write(self, findings: list[Finding], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")

        if not findings:
            body = '<div class="clean">No findings. Library looks clean.</div>'
        else:
            by_severity: dict[Severity, list[Finding]] = defaultdict(list)
            for f in findings:
                by_severity[f.severity].append(f)
            sections = []
            for severity in (Severity.ERROR, Severity.WARN, Severity.INFO):
                bucket = by_severity.get(severity, [])
                if not bucket:
                    continue
                sections.append(self._section(severity, bucket))
            body = "\n".join(sections)

        document = (
            "<!DOCTYPE html>\n"
            '<html lang="en"><head>'
            '<meta charset="utf-8">'
            "<title>Plex Audit Report</title>"
            f"<style>{_STYLES}</style>"
            "</head><body>"
            "<h1>Plex Audit Report</h1>"
            f'<div class="meta">Generated {html.escape(timestamp)} &middot; Total findings: {len(findings)}</div>'
            f"{body}"
            f"<script>{_SORT_SCRIPT}</script>"
            "</body></html>"
        )
        output_path.write_text(document, encoding="utf-8")

    def _section(self, severity: Severity, findings: list[Finding]) -> str:
        rows = []
        for f in findings:
            file_cell = f"<code>{html.escape(str(f.file_path))}</code>" if f.file_path else ""
            action_cell = html.escape(f.suggested_action) if f.suggested_action else ""
            rows.append(
                "<tr>"
                f"<td>{html.escape(f.check_id)}</td>"
                f"<td>{html.escape(f.title)}</td>"
                f"<td>{html.escape(f.subject)}</td>"
                f"<td>{file_cell}</td>"
                f"<td>{action_cell}</td>"
                "</tr>"
            )
        severity_class = f"sev-{severity.name.lower()}"
        return (
            f'<h2 class="{severity_class}">{severity.name} ({len(findings)})</h2>'
            "<table>"
            "<thead><tr><th>Check</th><th>Title</th><th>Subject</th><th>File</th><th>Suggested action</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
