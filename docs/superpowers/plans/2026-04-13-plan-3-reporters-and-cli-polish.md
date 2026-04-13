# Plan 3: Reporters + CLI Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the user-facing surface. Ship the remaining two reporters (JSON, HTML), extend the CLI to use all three based on config, add the `plex-audit init` wizard for first-time users, and add `plex-audit schedule --show` that prints a ready-to-paste cron/Task Scheduler line.

**Architecture:** Reporters each implement the `Reporter` protocol from `plex_audit/reporters/base.py`. CLI loops over `config.report.formats` and dispatches to the right reporter. Wizard is a separate Typer subcommand that prompts interactively, tests the Plex connection, writes `config.yaml`, and offers a scheduling snippet.

**Tech Stack:** Same as Plan 2 — Python 3.11+, pydantic v2, typer, python-plexapi. HTML reporter uses plain Python string templating (no Jinja) to avoid a new dep.

---

## File Structure

```
packages/plex_audit/
├── src/plex_audit/reporters/
│   ├── (existing) base.py
│   ├── (existing) markdown.py
│   ├── json.py              # Task 1
│   └── html.py              # Task 2
└── tests/
    ├── test_json_reporter.py
    └── test_html_reporter.py

packages/plex_audit_cli/
├── src/plex_audit_cli/
│   ├── (modify) main.py     # Task 3: loop over formats; Task 4+5: register new commands
│   ├── wizard.py            # Task 4
│   └── scheduler.py         # Task 5
└── tests/
    ├── test_multi_format.py
    ├── test_wizard.py
    └── test_scheduler.py
```

---

## Task 1: JSON reporter

**Files:**
- Create: `packages/plex_audit/src/plex_audit/reporters/json.py`
- Create: `packages/plex_audit/tests/test_json_reporter.py`
- Modify: `packages/plex_audit/src/plex_audit/reporters/__init__.py`

Output is a single JSON object: `{ "generated_at": ..., "total": N, "findings": [...] }`. Each finding serializes all fields; `Severity` → name string; `Category` → name string; `Path` → string; empty dicts elided for compactness; optional None fields omitted.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/test_json_reporter.py`:

```python
import json
from pathlib import Path

from plex_audit.reporters.json import JsonReporter
from plex_audit.types import Finding, Severity


def test_writes_valid_json_with_findings(tmp_path: Path):
    findings = [
        Finding(
            check_id="orphaned_files",
            severity=Severity.WARN,
            title="Orphaned file",
            subject="/m/x.mkv",
            details={"library": "Movies"},
            file_path=Path("/m/x.mkv"),
            suggested_action="Delete or add to Plex",
        ),
    ]
    output = tmp_path / "r.json"
    JsonReporter().write(findings, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["total"] == 1
    assert "generated_at" in payload
    assert payload["findings"][0]["check_id"] == "orphaned_files"
    assert payload["findings"][0]["severity"] == "WARN"
    assert payload["findings"][0]["file_path"] == "/m/x.mkv"
    assert payload["findings"][0]["details"] == {"library": "Movies"}


def test_empty_findings_valid_json(tmp_path: Path):
    output = tmp_path / "r.json"
    JsonReporter().write([], output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["total"] == 0
    assert payload["findings"] == []


def test_omits_none_optional_fields(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.INFO, title="t", subject="s"),
    ]
    output = tmp_path / "r.json"
    JsonReporter().write(findings, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    record = payload["findings"][0]
    assert "file_path" not in record
    assert "plex_item_id" not in record
    assert "suggested_action" not in record


def test_format_attr():
    assert JsonReporter.format == "json"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implementation**

`packages/plex_audit/src/plex_audit/reporters/json.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plex_audit.types import Finding


class JsonReporter:
    format = "json"

    def write(self, findings: list[Finding], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total": len(findings),
            "findings": [self._serialize(f) for f in findings],
        }
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")

    def _serialize(self, finding: Finding) -> dict[str, Any]:
        raw = asdict(finding)
        raw["severity"] = finding.severity.name
        if finding.file_path is not None:
            raw["file_path"] = str(finding.file_path)
        for key in ("file_path", "plex_item_id", "suggested_action"):
            if raw.get(key) is None:
                raw.pop(key, None)
        return raw
```

- [ ] **Step 4: Re-export** — update `packages/plex_audit/src/plex_audit/reporters/__init__.py` to include `JsonReporter`:

```python
from plex_audit.reporters.base import Reporter
from plex_audit.reporters.json import JsonReporter
from plex_audit.reporters.markdown import MarkdownReporter

__all__ = ["Reporter", "MarkdownReporter", "JsonReporter"]
```

- [ ] **Step 5: Run tests, ruff + mypy, commit**

```bash
uv run pytest -v
git add packages/plex_audit/src/plex_audit/reporters/json.py packages/plex_audit/src/plex_audit/reporters/__init__.py packages/plex_audit/tests/test_json_reporter.py
git commit -m "feat(reporters): add JSON reporter"
```

---

## Task 2: HTML reporter

**Files:**
- Create: `packages/plex_audit/src/plex_audit/reporters/html.py`
- Create: `packages/plex_audit/tests/test_html_reporter.py`
- Modify: `packages/plex_audit/src/plex_audit/reporters/__init__.py`

Self-contained HTML page: embedded CSS for severity color coding, a sortable `<table>` per severity, a header with generation timestamp and total count. No external assets, no JavaScript frameworks — a small inline `<script>` handles click-to-sort columns.

Escaping: all finding fields run through `html.escape`. Paths render as `<code>`.

- [ ] **Step 1: Tests**

`packages/plex_audit/tests/test_html_reporter.py`:

```python
from pathlib import Path

from plex_audit.reporters.html import HtmlReporter
from plex_audit.types import Finding, Severity


def test_renders_header_and_counts(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.WARN, title="t", subject="thing"),
        Finding(check_id="c", severity=Severity.ERROR, title="t", subject="oof"),
    ]
    output = tmp_path / "r.html"
    HtmlReporter().write(findings, output)
    html = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Plex Audit Report" in html
    assert "Total findings: 2" in html
    assert "thing" in html
    assert "oof" in html


def test_escapes_html_in_finding_fields(tmp_path: Path):
    findings = [Finding(check_id="c", severity=Severity.INFO, title="<script>alert(1)</script>", subject="s")]
    output = tmp_path / "r.html"
    HtmlReporter().write(findings, output)
    html = output.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_findings_renders_clean_message(tmp_path: Path):
    output = tmp_path / "r.html"
    HtmlReporter().write([], output)
    html = output.read_text(encoding="utf-8")
    assert "No findings" in html


def test_severity_sections_ordered(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.INFO, title="t", subject="i"),
        Finding(check_id="c", severity=Severity.ERROR, title="t", subject="e"),
    ]
    output = tmp_path / "r.html"
    HtmlReporter().write(findings, output)
    html = output.read_text(encoding="utf-8")
    assert html.index("ERROR") < html.index("INFO")


def test_format_attr():
    assert HtmlReporter.format == "html"
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implementation**

`packages/plex_audit/src/plex_audit/reporters/html.py`:

```python
from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime, timezone
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
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

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
```

- [ ] **Step 4: Re-export in `reporters/__init__.py`**

```python
from plex_audit.reporters.base import Reporter
from plex_audit.reporters.html import HtmlReporter
from plex_audit.reporters.json import JsonReporter
from plex_audit.reporters.markdown import MarkdownReporter

__all__ = ["Reporter", "MarkdownReporter", "JsonReporter", "HtmlReporter"]
```

- [ ] **Step 5: Run tests, ruff + mypy, commit**

```bash
uv run pytest -v
git add packages/plex_audit/src/plex_audit/reporters/html.py packages/plex_audit/src/plex_audit/reporters/__init__.py packages/plex_audit/tests/test_html_reporter.py
git commit -m "feat(reporters): add HTML reporter with severity-colored sortable tables"
```

---

## Task 3: CLI dispatches to all three reporters based on config

**Files:**
- Modify: `packages/plex_audit_cli/src/plex_audit_cli/main.py`
- Create: `packages/plex_audit_cli/tests/test_multi_format.py`

Currently the CLI's scan command only writes markdown. Add a dispatch dict so config `formats: [md, json, html]` writes three files.

- [ ] **Step 1: Test (write first)**

`packages/plex_audit_cli/tests/test_multi_format.py`:

```python
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from plex_audit_cli.main import app

runner = CliRunner()

CONFIG = """
plex:
  url: http://x
  token: t
paths:
  mappings: []
checks:
  enabled: []
  disabled: []
report:
  formats: [md, json, html]
  output_dir: "{out}"
  filename_template: "plex-audit-{{timestamp}}"
logging:
  level: INFO
  file: ./plex-audit.log
"""


def test_writes_all_three_formats(tmp_path: Path):
    out = tmp_path / "reports"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG.format(out=out.as_posix()), encoding="utf-8")

    with patch("plex_audit_cli.main.PlexClient") as plex_cls:
        plex_cls.return_value.iter_libraries.return_value = []
        result = runner.invoke(app, ["scan", "--config", str(cfg)])

    assert result.exit_code == 0, result.stdout
    assert len(list(out.glob("*.md"))) == 1
    assert len(list(out.glob("*.json"))) == 1
    assert len(list(out.glob("*.html"))) == 1
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Update `main.py` scan command**

Find this block in `packages/plex_audit_cli/src/plex_audit_cli/main.py`:

```python
    findings = sink.all()
    for fmt in config.report.formats:
        if fmt == "md":
            MarkdownReporter().write(findings, _output_path(config, "md"))
```

Replace with:

```python
    findings = sink.all()
    reporters = {
        "md": MarkdownReporter,
        "json": JsonReporter,
        "html": HtmlReporter,
    }
    for fmt in config.report.formats:
        reporter_cls = reporters.get(fmt)
        if reporter_cls is None:
            continue
        reporter_cls().write(findings, _output_path(config, fmt))
```

Also add imports at the top of the file (alongside the existing `from plex_audit.reporters.markdown import MarkdownReporter`):

```python
from plex_audit.reporters.html import HtmlReporter
from plex_audit.reporters.json import JsonReporter
```

- [ ] **Step 4: Run tests, commit**

```bash
uv run pytest -v
git add packages/plex_audit_cli/src/plex_audit_cli/main.py packages/plex_audit_cli/tests/test_multi_format.py
git commit -m "feat(cli): dispatch to markdown/json/html reporters based on config"
```

---

## Task 4: `plex-audit init` wizard

**Files:**
- Create: `packages/plex_audit_cli/src/plex_audit_cli/wizard.py`
- Create: `packages/plex_audit_cli/tests/test_wizard.py`
- Modify: `packages/plex_audit_cli/src/plex_audit_cli/main.py`

Interactive prompts write a valid `config.yaml`. Flow:
1. Prompt Plex URL (default `http://localhost:32400`).
2. Prompt Plex token (help link: `https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/`).
3. Test connection; on success print the discovered libraries.
4. For each discovered library, prompt the local path or blank to skip.
5. Prompt report formats (default `md`; accept comma-separated).
6. Prompt output directory (default `./reports`).
7. Write `config.yaml` to the path the user passed (default `./config.yaml`).
8. Print a sample `schedule --show` hint.

Tests drive the flow non-interactively by providing the inputs to Typer's `CliRunner`.

- [ ] **Step 1: Tests**

`packages/plex_audit_cli/tests/test_wizard.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from plex_audit_cli.main import app
from plex_audit.plex_client import Library

runner = CliRunner()


def _fake_plex_with_one_library() -> MagicMock:
    lib = Library(title="Movies", kind="movie", raw=MagicMock())
    plex = MagicMock()
    plex.iter_libraries.return_value = [lib]
    # Pre-populate the plexapi call path so the wizard can read the server section's Location.path
    lib.raw.locations = ["/media/movies"]
    return plex


def test_wizard_writes_config(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"

    inputs = "\n".join([
        "http://localhost:32400",       # url
        "tkn",                          # token
        str(tmp_path / "movies-local"), # local for Movies
        "md,json",                      # formats
        str(tmp_path / "reports"),      # output_dir
    ]) + "\n"

    with patch("plex_audit_cli.wizard.PlexClient") as plex_cls:
        plex_cls.return_value = _fake_plex_with_one_library()
        result = runner.invoke(app, ["init", "--config", str(cfg_path)], input=inputs)

    assert result.exit_code == 0, result.stdout
    assert cfg_path.exists()
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["plex"]["url"] == "http://localhost:32400"
    assert data["plex"]["token"] == "tkn"
    assert data["paths"]["mappings"][0]["plex"] == "/media/movies"
    assert data["paths"]["mappings"][0]["local"] == str(tmp_path / "movies-local")
    assert data["report"]["formats"] == ["md", "json"]
    assert data["report"]["output_dir"] == str(tmp_path / "reports")


def test_wizard_aborts_when_plex_unreachable(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    inputs = "http://x\nbad-token\n"
    with patch("plex_audit_cli.wizard.PlexClient") as plex_cls:
        plex_cls.return_value.iter_libraries.side_effect = ConnectionError("nope")
        result = runner.invoke(app, ["init", "--config", str(cfg_path)], input=inputs)
    assert result.exit_code != 0
    assert not cfg_path.exists()
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement `wizard.py`**

`packages/plex_audit_cli/src/plex_audit_cli/wizard.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from plex_audit.plex_client import PlexClient
from plex_audit.config import PlexConfig

TOKEN_HELP_URL = "https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/"


def run_wizard(config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config.yaml")) -> None:
    """Interactively build config.yaml."""
    typer.echo("plex-audit init — this will create a config.yaml for your Plex server.\n")

    url = typer.prompt("Plex URL", default="http://localhost:32400")
    typer.echo(f"(Need your token? See {TOKEN_HELP_URL})")
    token = typer.prompt("Plex token", hide_input=True)

    client = PlexClient(PlexConfig(url=url, token=token))
    try:
        libraries = list(client.iter_libraries())
    except Exception as exc:
        typer.secho(f"Could not reach Plex: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"\nFound {len(libraries)} libraries:")
    for lib in libraries:
        typer.echo(f"  - [{lib.kind}] {lib.title}")
    typer.echo()

    mappings: list[dict[str, str]] = []
    for lib in libraries:
        remote_paths = list(getattr(lib.raw, "locations", None) or [])
        if not remote_paths:
            continue
        for remote_path in remote_paths:
            local = typer.prompt(
                f"Local path for Plex library '{lib.title}' (Plex sees {remote_path}, or blank to skip)",
                default="",
                show_default=False,
            )
            if local.strip():
                mappings.append({"plex": remote_path, "local": local.strip()})

    formats_raw = typer.prompt("Report formats (comma-separated from md,json,html)", default="md")
    formats = [f.strip() for f in formats_raw.split(",") if f.strip()]

    output_dir = typer.prompt("Output directory for reports", default="./reports")

    config = {
        "plex": {"url": url, "token": token, "verify_ssl": True, "timeout_seconds": 30},
        "paths": {"mappings": mappings},
        "checks": {"enabled": "all", "disabled": [], "config": {}},
        "report": {
            "formats": formats,
            "output_dir": output_dir,
            "filename_template": "plex-audit-{timestamp}",
        },
        "logging": {"level": "INFO", "file": "./plex-audit.log"},
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    typer.secho(f"\nWrote {config_path}", fg=typer.colors.GREEN)
    typer.echo(f"Run `plex-audit scan --config {config_path}` to audit.")
    typer.echo(f"Run `plex-audit schedule --show --config {config_path}` for a cron/scheduled-task template.")
```

- [ ] **Step 4: Register `init` in main.py**

At the bottom of `main.py` (before the `if __name__ == "__main__":` block), add:

```python
from plex_audit_cli.wizard import run_wizard

app.command(name="init")(run_wizard)
```

- [ ] **Step 5: Run tests, commit**

```bash
uv run pytest -v
git add packages/plex_audit_cli/src/plex_audit_cli/wizard.py packages/plex_audit_cli/src/plex_audit_cli/main.py packages/plex_audit_cli/tests/test_wizard.py
git commit -m "feat(cli): add plex-audit init wizard"
```

---

## Task 5: `plex-audit schedule --show` cron/schtasks emitter

**Files:**
- Create: `packages/plex_audit_cli/src/plex_audit_cli/scheduler.py`
- Create: `packages/plex_audit_cli/tests/test_scheduler.py`
- Modify: `packages/plex_audit_cli/src/plex_audit_cli/main.py`

Prints a platform-appropriate snippet that runs `plex-audit scan --config <path>` on a schedule. No execution — just emits the text. Platform detection via `platform.system()`; `--os` override for CI snapshots.

- [ ] **Step 1: Tests**

`packages/plex_audit_cli/tests/test_scheduler.py`:

```python
from pathlib import Path

from typer.testing import CliRunner

from plex_audit_cli.main import app

runner = CliRunner()


def _write_config(tmp_path: Path) -> Path:
    body = """
plex: {url: http://x, token: t}
paths: {mappings: []}
checks: {enabled: all, disabled: []}
report: {formats: [md], output_dir: ./r, filename_template: "plex-audit-{timestamp}"}
logging: {level: INFO, file: ./plex-audit.log}
"""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(body, encoding="utf-8")
    return cfg


def test_show_cron_snippet(tmp_path: Path):
    cfg = _write_config(tmp_path)
    result = runner.invoke(app, ["schedule", "--show", "--os", "linux", "--config", str(cfg)])
    assert result.exit_code == 0, result.stdout
    assert "0 3 * * *" in result.stdout
    assert "plex-audit scan" in result.stdout
    assert str(cfg) in result.stdout


def test_show_schtasks_snippet(tmp_path: Path):
    cfg = _write_config(tmp_path)
    result = runner.invoke(app, ["schedule", "--show", "--os", "windows", "--config", str(cfg)])
    assert result.exit_code == 0, result.stdout
    assert "schtasks /Create" in result.stdout
    assert "PlexAudit" in result.stdout
    assert str(cfg) in result.stdout


def test_show_requires_show_flag(tmp_path: Path):
    cfg = _write_config(tmp_path)
    result = runner.invoke(app, ["schedule", "--os", "linux", "--config", str(cfg)])
    # Without --show the command exits non-zero with a helpful message.
    assert result.exit_code != 0
```

- [ ] **Step 2: Implement `scheduler.py`**

```python
from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Annotated

import typer

SUPPORTED_OS = ("linux", "macos", "windows")


def show_schedule(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("config.yaml"),
    show: Annotated[bool, typer.Option("--show", help="Print the schedule snippet.")] = False,
    target_os: Annotated[str | None, typer.Option("--os", help="Override detected OS (linux, macos, windows).")] = None,
) -> None:
    """Emit a scheduled-task snippet for your OS."""
    if not show:
        typer.secho("Pass --show to print the snippet.", err=True, fg=typer.colors.YELLOW)
        raise typer.Exit(code=2)

    detected = (target_os or _detect_os()).lower()
    if detected not in SUPPORTED_OS:
        typer.secho(f"Unsupported OS: {detected}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2)

    exe = Path(sys.argv[0]).name or "plex-audit"

    if detected in ("linux", "macos"):
        typer.echo("# Add this to your crontab (runs daily at 03:00):")
        typer.echo(f"0 3 * * * {exe} scan --config {config_path}")
    else:
        typer.echo("REM Run daily at 03:00. Adjust /TN as desired.")
        typer.echo(
            f'schtasks /Create /SC DAILY /TN "PlexAudit" /TR '
            f'"\\"{exe}\\" scan --config \\"{config_path}\\"" /ST 03:00 /F'
        )


def _detect_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system
```

- [ ] **Step 3: Register `schedule` in main.py**

Add below the `init` registration:

```python
from plex_audit_cli.scheduler import show_schedule

app.command(name="schedule")(show_schedule)
```

- [ ] **Step 4: Run tests, commit**

```bash
uv run pytest -v
git add packages/plex_audit_cli/src/plex_audit_cli/scheduler.py packages/plex_audit_cli/src/plex_audit_cli/main.py packages/plex_audit_cli/tests/test_scheduler.py
git commit -m "feat(cli): add schedule --show with cron and schtasks templates"
```

---

## Self-review notes

- Spec coverage: JSON/HTML reporters + multi-format dispatch (Tasks 1–3); `plex-audit init` wizard (Task 4); `plex-audit schedule --show` (Task 5). That's the full Plan 3 scope per the design doc's §6 (CLI polish).
- Placeholder scan: every step has concrete code or concrete commands.
- Type consistency: `Reporter` protocol in `reporters/base.py` (from Plan 1) has `format: str` class attribute and `write(findings, path) -> None`. Every reporter in this plan matches that signature exactly.
- The wizard reads `lib.raw.locations` to discover a library's Plex-reported path. That attribute comes from plexapi's LibrarySection. If the user runs the wizard against a real Plex server, `locations` is a list of strings — the code handles zero, one, or many.
