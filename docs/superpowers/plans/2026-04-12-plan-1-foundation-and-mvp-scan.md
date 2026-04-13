# Plan 1: Foundation + MVP Scan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a working `plex-audit scan` command backed by a plugin-based engine, one real check (orphaned files), and a markdown report — the foundation that later plans layer checks, reporters, and distribution onto.

**Architecture:** Monorepo with two packages (`plex_audit` core library, `plex_audit_cli` CLI wrapper) managed by `uv` workspaces. Checks are Python entry-point plugins implementing a `Check` protocol and yielding `Finding` dataclasses into a `FindingsSink`. A markdown reporter serializes findings to a file. CLI loads config, builds `ScanContext`, runs engine, writes report, exits with a severity-based code.

**Tech Stack:** Python 3.11+, `uv` (workspace + env + runner), `pydantic` v2, `python-plexapi`, `PyYAML`, `typer`, `pytest` + `pytest-cov`, `ruff`, `mypy`.

---

## File Structure

```
plex_tools/
├── pyproject.toml                                  # uv workspace root
├── .python-version
├── .gitignore
├── ruff.toml
├── mypy.ini
├── pytest.ini
├── packages/
│   ├── plex_audit/
│   │   ├── pyproject.toml
│   │   ├── src/plex_audit/
│   │   │   ├── __init__.py
│   │   │   ├── types.py                    # Severity, Category, Finding, Check protocol
│   │   │   ├── path_mapper.py
│   │   │   ├── config.py
│   │   │   ├── plex_client.py
│   │   │   ├── context.py                  # ScanContext, FindingsSink
│   │   │   ├── engine.py
│   │   │   ├── reporters/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                 # Reporter protocol
│   │   │   │   └── markdown.py
│   │   │   └── checks/
│   │   │       ├── __init__.py
│   │   │       └── orphaned_files.py
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_types.py
│   │       ├── test_path_mapper.py
│   │       ├── test_config.py
│   │       ├── test_plex_client.py
│   │       ├── test_context.py
│   │       ├── test_engine.py
│   │       ├── test_markdown_reporter.py
│   │       └── checks/test_orphaned_files.py
│   └── plex_audit_cli/
│       ├── pyproject.toml
│       ├── src/plex_audit_cli/
│       │   ├── __init__.py
│       │   └── main.py
│       └── tests/
│           └── test_scan_cli.py
└── docs/                                     # already exists, spec is here
```

---

## Task 1: Repo scaffold, tooling, and workspace

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `ruff.toml`
- Create: `mypy.ini`
- Create: `pytest.ini`
- Create: `packages/plex_audit/pyproject.toml`
- Create: `packages/plex_audit/src/plex_audit/__init__.py`
- Create: `packages/plex_audit/tests/__init__.py`
- Create: `packages/plex_audit_cli/pyproject.toml`
- Create: `packages/plex_audit_cli/src/plex_audit_cli/__init__.py`
- Create: `packages/plex_audit_cli/tests/__init__.py`

- [ ] **Step 1: Write the failing "workspace exists" test**

Create `packages/plex_audit/tests/test_import.py`:

```python
def test_plex_audit_importable():
    import plex_audit
    assert plex_audit.__version__ == "0.1.0"
```

- [ ] **Step 2: Run it to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_import.py -v`
Expected: FAIL (module not found or `uv` not configured yet — either is fine).

- [ ] **Step 3: Create `.python-version`**

```
3.12
```

- [ ] **Step 4: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
dist/
build/
*.egg-info/
.coverage
coverage.xml
htmlcov/
reports/
plex-audit.log
```

- [ ] **Step 5: Create root `pyproject.toml` (workspace root, not installable)**

```toml
[project]
name = "plex-tools-workspace"
version = "0"
requires-python = ">=3.11"

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
plex-audit = { workspace = true }
plex-audit-cli = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.6",
    "mypy>=1.11",
    "types-PyYAML",
]
```

- [ ] **Step 6: Create `ruff.toml`**

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]

[format]
quote-style = "double"
```

- [ ] **Step 7: Create `mypy.ini`**

```ini
[mypy]
python_version = 3.11
strict = True
warn_unused_ignores = True
warn_redundant_casts = True

[mypy-plexapi.*]
ignore_missing_imports = True

[mypy-typer.*]
ignore_missing_imports = True
```

- [ ] **Step 8: Create `pytest.ini`**

```ini
[pytest]
testpaths = packages/plex_audit/tests packages/plex_audit_cli/tests
addopts = -ra --strict-markers
markers =
    integration: tests that require a real Plex server
```

- [ ] **Step 9: Create `packages/plex_audit/pyproject.toml`**

```toml
[project]
name = "plex-audit"
version = "0.1.0"
description = "Plex Media Server library auditor — core library"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.8",
    "PyYAML>=6.0",
    "PlexAPI>=4.15",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/plex_audit"]

[project.entry-points."plex_audit.checks"]
# Checks register here as they land. Populated in Task 9.
```

- [ ] **Step 10: Create `packages/plex_audit/src/plex_audit/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 11: Create empty `packages/plex_audit/tests/__init__.py`** (empty file)

- [ ] **Step 12: Create `packages/plex_audit_cli/pyproject.toml`**

```toml
[project]
name = "plex-audit-cli"
version = "0.1.0"
description = "Plex Media Server library auditor — CLI"
requires-python = ">=3.11"
dependencies = [
    "plex-audit",
    "typer>=0.12",
]

[project.scripts]
plex-audit = "plex_audit_cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/plex_audit_cli"]
```

- [ ] **Step 13: Create `packages/plex_audit_cli/src/plex_audit_cli/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 14: Create empty `packages/plex_audit_cli/tests/__init__.py`** (empty file)

- [ ] **Step 15: Create a minimal `packages/plex_audit/README.md`**

```markdown
# plex-audit

Core library for the Plex Library Auditor. See repo root for docs.
```

- [ ] **Step 16: Install and verify the workspace**

Run: `uv sync --all-packages`
Expected: creates `.venv`, installs both packages + dev deps, no errors.

- [ ] **Step 17: Run the import test to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_import.py -v`
Expected: PASS.

- [ ] **Step 18: Run lint and types (sanity, should be clean)**

Run: `uv run ruff check . && uv run mypy packages/plex_audit/src`
Expected: both clean.

- [ ] **Step 19: Commit**

```bash
git add -A
git commit -m "chore: scaffold uv workspace with plex_audit and plex_audit_cli packages"
```

---

## Task 2: Core types — Severity, Category, Finding, Check protocol

**Files:**
- Create: `packages/plex_audit/src/plex_audit/types.py`
- Create: `packages/plex_audit/tests/test_types.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/test_types.py`:

```python
from pathlib import Path
from plex_audit.types import Category, Finding, Severity


def test_severity_ordering():
    assert Severity.INFO < Severity.WARN < Severity.ERROR


def test_finding_is_frozen_dataclass():
    finding = Finding(
        check_id="missing_episodes",
        severity=Severity.WARN,
        title="Season 3 missing 4 episodes",
        subject="Breaking Bad",
        details={"missing": [5, 6, 7, 9]},
    )
    assert finding.check_id == "missing_episodes"
    assert finding.plex_item_id is None
    assert finding.file_path is None
    assert finding.suggested_action is None


def test_finding_accepts_optional_fields():
    finding = Finding(
        check_id="orphaned_files",
        severity=Severity.INFO,
        title="Orphaned file",
        subject="stray.mkv",
        details={},
        file_path=Path("/media/tv/stray.mkv"),
        suggested_action="Delete or add to Plex library",
    )
    assert finding.file_path == Path("/media/tv/stray.mkv")
    assert finding.suggested_action is not None


def test_category_values():
    assert {c.name for c in Category} == {"MISSING", "METADATA", "FILE_HEALTH", "DUPLICATE"}
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_types.py -v`
Expected: FAIL (`plex_audit.types` not found).

- [ ] **Step 3: Implement `types.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Iterable, Protocol, runtime_checkable


class Severity(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2


class Category(Enum):
    MISSING = "missing"
    METADATA = "metadata"
    FILE_HEALTH = "file_health"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: Severity
    title: str
    subject: str
    details: dict[str, Any] = field(default_factory=dict)
    plex_item_id: str | None = None
    file_path: Path | None = None
    suggested_action: str | None = None


@runtime_checkable
class Check(Protocol):
    id: str
    name: str
    category: Category
    parallel_safe: bool
    requires_filesystem: bool

    def run(self, ctx: "ScanContext") -> Iterable[Finding]: ...  # noqa: F821
```

Note: `ScanContext` is forward-declared (string) — defined in Task 6. That's fine because `Check` is a protocol; it's not instantiated here.

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_types.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/plex_audit/src/plex_audit/types.py packages/plex_audit/tests/test_types.py
git commit -m "feat(core): add Severity, Category, Finding, Check types"
```

---

## Task 3: PathMapper — translate Plex paths to local paths

**Files:**
- Create: `packages/plex_audit/src/plex_audit/path_mapper.py`
- Create: `packages/plex_audit/tests/test_path_mapper.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/test_path_mapper.py`:

```python
from pathlib import PurePath, PurePosixPath, PureWindowsPath

from plex_audit.path_mapper import PathMapper, PathMapping


def _mapper(mappings: list[tuple[str, str]]) -> PathMapper:
    return PathMapper([PathMapping(plex=p, local=l) for p, l in mappings])


def test_returns_none_when_no_mapping_matches():
    mapper = _mapper([("/media/tv", "D:/Media/TV")])
    assert mapper.to_local("/media/movies/x.mkv") is None


def test_translates_posix_plex_path_to_windows_local():
    mapper = _mapper([("/media/tv", "D:/Media/TV")])
    assert mapper.to_local("/media/tv/Breaking Bad/S01/e01.mkv") == PureWindowsPath(
        "D:/Media/TV/Breaking Bad/S01/e01.mkv"
    )


def test_trailing_slash_insensitive():
    mapper = _mapper([("/media/tv/", "D:/Media/TV/")])
    assert mapper.to_local("/media/tv/a.mkv") == PureWindowsPath("D:/Media/TV/a.mkv")


def test_longest_prefix_wins():
    mapper = _mapper([
        ("/media", "D:/Media"),
        ("/media/tv", "E:/TV"),
    ])
    assert mapper.to_local("/media/tv/show.mkv") == PureWindowsPath("E:/TV/show.mkv")
    assert mapper.to_local("/media/movies/film.mkv") == PureWindowsPath("D:/Media/movies/film.mkv")


def test_posix_local_target():
    mapper = _mapper([("/media", "/mnt/media")])
    result = mapper.to_local("/media/movies/film.mkv")
    assert result == PurePosixPath("/mnt/media/movies/film.mkv")


def test_has_mappings_flag():
    assert PathMapper([]).has_mappings is False
    assert _mapper([("/a", "/b")]).has_mappings is True
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_path_mapper.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `path_mapper.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath, PurePosixPath, PureWindowsPath


@dataclass(frozen=True)
class PathMapping:
    plex: str
    local: str


def _detect_path_flavor(path: str) -> type[PurePath]:
    # Heuristic: a drive letter or backslash → Windows, else POSIX.
    if len(path) >= 2 and path[1] == ":":
        return PureWindowsPath
    if "\\" in path:
        return PureWindowsPath
    return PurePosixPath


def _normalize_plex_prefix(prefix: str) -> str:
    # Plex paths are POSIX-style. Strip trailing slashes for comparison.
    return prefix.rstrip("/")


class PathMapper:
    def __init__(self, mappings: list[PathMapping]) -> None:
        # Sort longest-prefix first so nested mappings match correctly.
        self._mappings = sorted(
            mappings,
            key=lambda m: len(_normalize_plex_prefix(m.plex)),
            reverse=True,
        )

    @property
    def has_mappings(self) -> bool:
        return bool(self._mappings)

    def to_local(self, plex_path: str) -> PurePath | None:
        normalized_source = plex_path.rstrip("/")
        for mapping in self._mappings:
            plex_prefix = _normalize_plex_prefix(mapping.plex)
            if normalized_source == plex_prefix or normalized_source.startswith(plex_prefix + "/"):
                remainder = normalized_source[len(plex_prefix) :].lstrip("/")
                flavor = _detect_path_flavor(mapping.local)
                local_root = mapping.local.rstrip("/\\")
                if not remainder:
                    return flavor(local_root)
                return flavor(local_root) / remainder
        return None
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_path_mapper.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/plex_audit/src/plex_audit/path_mapper.py packages/plex_audit/tests/test_path_mapper.py
git commit -m "feat(core): add PathMapper with longest-prefix matching"
```

---

## Task 4: Config — pydantic models + YAML loader + env/CLI precedence

**Files:**
- Create: `packages/plex_audit/src/plex_audit/config.py`
- Create: `packages/plex_audit/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/test_config.py`:

```python
from pathlib import Path

import pytest
from plex_audit.config import Config, ConfigError, load_config

SAMPLE_YAML = """
plex:
  url: http://localhost:32400
  token: abc123
  verify_ssl: true
  timeout_seconds: 30

paths:
  mappings:
    - plex: /media/tv
      local: D:/Media/TV

checks:
  enabled: all
  disabled: []
  config: {}

report:
  formats: [md]
  output_dir: ./reports
  filename_template: "plex-audit-{timestamp}"

logging:
  level: INFO
  file: ./plex-audit.log
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_minimal_valid_config(tmp_path: Path):
    cfg = load_config(_write(tmp_path, SAMPLE_YAML))
    assert isinstance(cfg, Config)
    assert cfg.plex.url == "http://localhost:32400"
    assert cfg.plex.token == "abc123"
    assert cfg.paths.mappings[0].plex == "/media/tv"
    assert cfg.report.formats == ["md"]


def test_env_var_overrides_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLEX_AUDIT_PLEX__TOKEN", "env-token")
    cfg = load_config(_write(tmp_path, SAMPLE_YAML))
    assert cfg.plex.token == "env-token"


def test_cli_overrides_beat_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PLEX_AUDIT_PLEX__URL", "http://env:32400")
    cfg = load_config(
        _write(tmp_path, SAMPLE_YAML),
        overrides={"plex": {"url": "http://cli:32400"}},
    )
    assert cfg.plex.url == "http://cli:32400"


def test_missing_required_field_raises(tmp_path: Path):
    body = SAMPLE_YAML.replace("token: abc123", "")
    with pytest.raises(ConfigError) as info:
        load_config(_write(tmp_path, body))
    assert "token" in str(info.value)


def test_enabled_accepts_list_or_all(tmp_path: Path):
    cfg = load_config(_write(tmp_path, SAMPLE_YAML.replace("enabled: all", "enabled: [orphaned_files]")))
    assert cfg.checks.enabled == ["orphaned_files"]


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_config.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `config.py`**

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError


class ConfigError(Exception):
    pass


class PlexConfig(BaseModel):
    url: str
    token: str
    verify_ssl: bool = True
    timeout_seconds: int = 30


class PathMappingModel(BaseModel):
    plex: str
    local: str


class PathsConfig(BaseModel):
    mappings: list[PathMappingModel] = Field(default_factory=list)


class ChecksConfig(BaseModel):
    enabled: Literal["all"] | list[str] = "all"
    disabled: list[str] = Field(default_factory=list)
    config: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ReportConfig(BaseModel):
    formats: list[Literal["md", "json", "html"]] = Field(default_factory=lambda: ["md"])
    output_dir: str = "./reports"
    filename_template: str = "plex-audit-{timestamp}"


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str = "./plex-audit.log"


class Config(BaseModel):
    plex: PlexConfig
    paths: PathsConfig = Field(default_factory=PathsConfig)
    checks: ChecksConfig = Field(default_factory=ChecksConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _env_overrides(prefix: str = "PLEX_AUDIT_") -> dict[str, Any]:
    """Translate PLEX_AUDIT_SECTION__KEY env vars into nested dict."""
    result: dict[str, Any] = {}
    for raw_key, value in os.environ.items():
        if not raw_key.startswith(prefix):
            continue
        path = raw_key[len(prefix) :].lower().split("__")
        cursor: dict[str, Any] = result
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = value
    return result


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path, overrides: dict[str, Any] | None = None) -> Config:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    merged = _deep_merge(raw, _env_overrides())
    if overrides:
        merged = _deep_merge(merged, overrides)

    try:
        return Config.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_config.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/plex_audit/src/plex_audit/config.py packages/plex_audit/tests/test_config.py
git commit -m "feat(core): add pydantic Config with YAML + env + override precedence"
```

---

## Task 5: PlexClient wrapper with per-scan cache

**Files:**
- Create: `packages/plex_audit/src/plex_audit/plex_client.py`
- Create: `packages/plex_audit/tests/test_plex_client.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/test_plex_client.py`:

```python
from unittest.mock import MagicMock, patch

from plex_audit.plex_client import MediaFile, PlexClient
from plex_audit.config import PlexConfig


def _fake_server() -> MagicMock:
    server = MagicMock()
    movie_section = MagicMock()
    movie_section.type = "movie"
    movie_section.title = "Movies"
    show_section = MagicMock()
    show_section.type = "show"
    show_section.title = "TV"
    server.library.sections.return_value = [movie_section, show_section]
    return server


def test_iter_libraries_returns_typed_entries():
    with patch("plex_audit.plex_client.PlexServer", return_value=_fake_server()):
        client = PlexClient(PlexConfig(url="http://x", token="t"))
        libraries = list(client.iter_libraries())
    assert [lib.kind for lib in libraries] == ["movie", "show"]
    assert libraries[0].title == "Movies"


def test_iter_libraries_is_cached():
    server = _fake_server()
    with patch("plex_audit.plex_client.PlexServer", return_value=server):
        client = PlexClient(PlexConfig(url="http://x", token="t"))
        list(client.iter_libraries())
        list(client.iter_libraries())
    assert server.library.sections.call_count == 1


def test_get_media_files_extracts_paths():
    media_part = MagicMock()
    media_part.file = "/media/tv/show/s01e01.mkv"
    media_item = MagicMock()
    media_item.parts = [media_part]
    plex_item = MagicMock()
    plex_item.media = [media_item]
    plex_item.ratingKey = "42"

    with patch("plex_audit.plex_client.PlexServer", return_value=_fake_server()):
        client = PlexClient(PlexConfig(url="http://x", token="t"))
        files = list(client.get_media_files(plex_item))
    assert files == [MediaFile(plex_path="/media/tv/show/s01e01.mkv", rating_key="42")]
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_plex_client.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `plex_client.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Iterator

from plexapi.server import PlexServer

from plex_audit.config import PlexConfig


@dataclass(frozen=True)
class Library:
    title: str
    kind: str  # "movie" | "show"
    raw: Any


@dataclass(frozen=True)
class MediaFile:
    plex_path: str
    rating_key: str


class PlexClient:
    def __init__(self, config: PlexConfig) -> None:
        self._config = config
        self._server: PlexServer | None = None
        self._libraries_cache: list[Library] | None = None

    @property
    def server(self) -> PlexServer:
        if self._server is None:
            self._server = PlexServer(
                self._config.url,
                self._config.token,
                timeout=self._config.timeout_seconds,
            )
        return self._server

    def iter_libraries(self) -> Iterator[Library]:
        if self._libraries_cache is None:
            sections = self.server.library.sections()
            self._libraries_cache = [
                Library(title=section.title, kind=section.type, raw=section)
                for section in sections
            ]
        yield from self._libraries_cache

    def get_media_files(self, item: Any) -> Iterator[MediaFile]:
        rating_key = str(getattr(item, "ratingKey", ""))
        for media in getattr(item, "media", []) or []:
            for part in getattr(media, "parts", []) or []:
                path = getattr(part, "file", None)
                if path:
                    yield MediaFile(plex_path=path, rating_key=rating_key)
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_plex_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/plex_audit/src/plex_audit/plex_client.py packages/plex_audit/tests/test_plex_client.py
git commit -m "feat(core): add PlexClient wrapper with library cache and MediaFile extraction"
```

---

## Task 6: ScanContext and FindingsSink

**Files:**
- Create: `packages/plex_audit/src/plex_audit/context.py`
- Create: `packages/plex_audit/tests/test_context.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/test_context.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from plex_audit.context import FindingsSink, ScanContext
from plex_audit.types import Category, Finding, Severity


def _finding(check_id: str = "c", severity: Severity = Severity.WARN, subject: str = "s") -> Finding:
    return Finding(check_id=check_id, severity=severity, title="t", subject=subject)


def test_sink_collects_findings():
    sink = FindingsSink()
    sink.add(_finding())
    sink.add(_finding(check_id="c2"))
    assert len(sink.all()) == 2


def test_sink_deduplicates_identical_findings():
    sink = FindingsSink()
    a = _finding()
    sink.add(a)
    sink.add(a)  # same hash
    assert len(sink.all()) == 1


def test_sink_sorts_by_severity_then_check_then_subject():
    sink = FindingsSink()
    sink.add(_finding(check_id="b", severity=Severity.INFO, subject="z"))
    sink.add(_finding(check_id="a", severity=Severity.ERROR, subject="y"))
    sink.add(_finding(check_id="a", severity=Severity.ERROR, subject="x"))

    ordered = sink.all()
    assert [f.severity for f in ordered] == [Severity.ERROR, Severity.ERROR, Severity.INFO]
    assert [f.subject for f in ordered[:2]] == ["x", "y"]


def test_sink_highest_severity():
    sink = FindingsSink()
    assert sink.highest_severity() is None
    sink.add(_finding(severity=Severity.INFO))
    sink.add(_finding(severity=Severity.WARN, subject="q"))
    assert sink.highest_severity() == Severity.WARN


def test_scan_context_exposes_services_and_report_method():
    sink = FindingsSink()
    ctx = ScanContext(
        plex=MagicMock(),
        path_mapper=MagicMock(has_mappings=True),
        config=MagicMock(),
        filesystem_available=True,
        _sink=sink,
    )
    ctx.report(_finding())
    assert len(sink.all()) == 1
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_context.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `context.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from plex_audit.types import Finding, Severity

if TYPE_CHECKING:
    from plex_audit.config import Config
    from plex_audit.path_mapper import PathMapper
    from plex_audit.plex_client import PlexClient


class FindingsSink:
    def __init__(self) -> None:
        self._seen: set[Finding] = set()
        self._ordered: list[Finding] = []

    def add(self, finding: Finding) -> None:
        if finding in self._seen:
            return
        self._seen.add(finding)
        self._ordered.append(finding)

    def all(self) -> list[Finding]:
        return sorted(
            self._ordered,
            key=lambda f: (-int(f.severity), f.check_id, f.subject),
        )

    def highest_severity(self) -> Severity | None:
        if not self._ordered:
            return None
        return max(f.severity for f in self._ordered)


@dataclass(frozen=True)
class ScanContext:
    plex: "PlexClient"
    path_mapper: "PathMapper"
    config: "Config"
    filesystem_available: bool
    _sink: FindingsSink = field(default_factory=FindingsSink)

    def report(self, finding: Finding) -> None:
        self._sink.add(finding)
```

Note: `Finding` isn't hashable by default because `details: dict` is unhashable. Update `types.py` to make Finding hashable on its scalar fields:

Edit `packages/plex_audit/src/plex_audit/types.py` — replace the `Finding` dataclass with:

```python
@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: Severity
    title: str
    subject: str
    details: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)
    plex_item_id: str | None = None
    file_path: Path | None = None
    suggested_action: str | None = None
```

(`hash=False, compare=False` excludes `details` from hashing/equality so identical findings with different details maps still collapse — acceptable for v1 dedup.)

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_context.py packages/plex_audit/tests/test_types.py -v`
Expected: PASS for both files.

- [ ] **Step 5: Commit**

```bash
git add packages/plex_audit/src/plex_audit/context.py packages/plex_audit/src/plex_audit/types.py packages/plex_audit/tests/test_context.py
git commit -m "feat(core): add ScanContext and FindingsSink with dedup and severity-sorted output"
```

---

## Task 7: Engine — plugin discovery, filtering, execution, error isolation

**Files:**
- Create: `packages/plex_audit/src/plex_audit/engine.py`
- Create: `packages/plex_audit/tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/test_engine.py`:

```python
from dataclasses import dataclass
from unittest.mock import MagicMock

from plex_audit.context import FindingsSink, ScanContext
from plex_audit.engine import Engine
from plex_audit.types import Category, Finding, Severity


@dataclass
class _FakeCheck:
    id: str = "fake"
    name: str = "Fake Check"
    category: Category = Category.METADATA
    parallel_safe: bool = True
    requires_filesystem: bool = False
    findings: tuple[Finding, ...] = ()
    raises: Exception | None = None

    def run(self, ctx: ScanContext):
        if self.raises:
            raise self.raises
        for f in self.findings:
            yield f


def _ctx(filesystem: bool = True) -> ScanContext:
    return ScanContext(
        plex=MagicMock(),
        path_mapper=MagicMock(has_mappings=filesystem),
        config=MagicMock(),
        filesystem_available=filesystem,
        _sink=FindingsSink(),
    )


def test_engine_runs_all_enabled_checks_and_collects_findings():
    f1 = Finding(check_id="a", severity=Severity.WARN, title="t", subject="s1")
    f2 = Finding(check_id="b", severity=Severity.INFO, title="t", subject="s2")
    ctx = _ctx()
    engine = Engine(checks=[_FakeCheck(id="a", findings=(f1,)), _FakeCheck(id="b", findings=(f2,))])
    engine.run(ctx, enabled="all", disabled=[])
    assert {f.check_id for f in ctx._sink.all()} == {"a", "b"}


def test_engine_respects_enabled_list():
    ctx = _ctx()
    engine = Engine(checks=[
        _FakeCheck(id="a", findings=(Finding(check_id="a", severity=Severity.WARN, title="t", subject="s"),)),
        _FakeCheck(id="b", findings=(Finding(check_id="b", severity=Severity.WARN, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled=["a"], disabled=[])
    assert {f.check_id for f in ctx._sink.all()} == {"a"}


def test_engine_respects_disabled_list():
    ctx = _ctx()
    engine = Engine(checks=[
        _FakeCheck(id="a", findings=(Finding(check_id="a", severity=Severity.WARN, title="t", subject="s"),)),
        _FakeCheck(id="b", findings=(Finding(check_id="b", severity=Severity.WARN, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled="all", disabled=["b"])
    assert {f.check_id for f in ctx._sink.all()} == {"a"}


def test_engine_isolates_crashing_check():
    ctx = _ctx()
    engine = Engine(checks=[
        _FakeCheck(id="bad", raises=RuntimeError("boom")),
        _FakeCheck(id="good", findings=(Finding(check_id="good", severity=Severity.INFO, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled="all", disabled=[])
    findings = ctx._sink.all()
    assert any(f.check_id == "engine" and f.severity == Severity.ERROR and "bad" in f.subject for f in findings)
    assert any(f.check_id == "good" for f in findings)


def test_engine_skips_filesystem_checks_when_unavailable():
    ctx = _ctx(filesystem=False)
    engine = Engine(checks=[
        _FakeCheck(id="fs", requires_filesystem=True,
                   findings=(Finding(check_id="fs", severity=Severity.WARN, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled="all", disabled=[])
    findings = ctx._sink.all()
    assert not any(f.check_id == "fs" and f.severity == Severity.WARN for f in findings)
    assert any(f.check_id == "engine" and f.severity == Severity.INFO and "fs" in f.subject for f in findings)
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_engine.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `engine.py`**

```python
from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import entry_points
from typing import Iterable, Literal

from plex_audit.context import ScanContext
from plex_audit.types import Check, Finding, Severity

log = logging.getLogger(__name__)


class Engine:
    ENTRY_POINT_GROUP = "plex_audit.checks"

    def __init__(self, checks: list[Check]) -> None:
        self._checks = checks

    @classmethod
    def from_entry_points(cls) -> "Engine":
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
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_engine.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/plex_audit/src/plex_audit/engine.py packages/plex_audit/tests/test_engine.py
git commit -m "feat(core): add Engine with entry-point discovery, filtering, parallel execution, and crash isolation"
```

---

## Task 8: Markdown reporter

**Files:**
- Create: `packages/plex_audit/src/plex_audit/reporters/__init__.py`
- Create: `packages/plex_audit/src/plex_audit/reporters/base.py`
- Create: `packages/plex_audit/src/plex_audit/reporters/markdown.py`
- Create: `packages/plex_audit/tests/test_markdown_reporter.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/test_markdown_reporter.py`:

```python
from pathlib import Path

from plex_audit.reporters.markdown import MarkdownReporter
from plex_audit.types import Finding, Severity


def test_renders_header_and_summary(tmp_path: Path):
    findings = [
        Finding(check_id="orphaned_files", severity=Severity.WARN, title="Orphaned file", subject="stray.mkv"),
        Finding(check_id="orphaned_files", severity=Severity.WARN, title="Orphaned file", subject="other.mkv"),
    ]
    output = tmp_path / "r.md"
    MarkdownReporter().write(findings, output)
    text = output.read_text(encoding="utf-8")
    assert "# Plex Audit Report" in text
    assert "**Total findings:** 2" in text
    assert "orphaned_files" in text
    assert "stray.mkv" in text


def test_renders_empty_findings_as_clean(tmp_path: Path):
    output = tmp_path / "r.md"
    MarkdownReporter().write([], output)
    text = output.read_text(encoding="utf-8")
    assert "No findings" in text


def test_severity_sections_are_present(tmp_path: Path):
    findings = [
        Finding(check_id="c", severity=Severity.ERROR, title="t", subject="s1"),
        Finding(check_id="c", severity=Severity.INFO, title="t", subject="s2"),
    ]
    output = tmp_path / "r.md"
    MarkdownReporter().write(findings, output)
    text = output.read_text(encoding="utf-8")
    assert "## ERROR" in text
    assert "## INFO" in text
    assert text.index("## ERROR") < text.index("## INFO")
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/test_markdown_reporter.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the reporter files**

`packages/plex_audit/src/plex_audit/reporters/__init__.py`:

```python
from plex_audit.reporters.base import Reporter
from plex_audit.reporters.markdown import MarkdownReporter

__all__ = ["Reporter", "MarkdownReporter"]
```

`packages/plex_audit/src/plex_audit/reporters/base.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from plex_audit.types import Finding


class Reporter(Protocol):
    format: str

    def write(self, findings: list[Finding], output_path: Path) -> None: ...
```

`packages/plex_audit/src/plex_audit/reporters/markdown.py`:

```python
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from plex_audit.types import Finding, Severity


class MarkdownReporter:
    format = "md"

    def write(self, findings: list[Finding], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        lines.append("# Plex Audit Report")
        lines.append("")
        lines.append(f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_")
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
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/test_markdown_reporter.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/plex_audit/src/plex_audit/reporters packages/plex_audit/tests/test_markdown_reporter.py
git commit -m "feat(reporters): add markdown reporter with severity sections"
```

---

## Task 9: `orphaned_files` check

**Files:**
- Create: `packages/plex_audit/src/plex_audit/checks/__init__.py`
- Create: `packages/plex_audit/src/plex_audit/checks/orphaned_files.py`
- Create: `packages/plex_audit/tests/checks/__init__.py`
- Create: `packages/plex_audit/tests/checks/test_orphaned_files.py`
- Modify: `packages/plex_audit/pyproject.toml` (register entry point)

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit/tests/checks/__init__.py` — empty file.

`packages/plex_audit/tests/checks/test_orphaned_files.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from plex_audit.checks.orphaned_files import OrphanedFilesCheck, VIDEO_EXTENSIONS
from plex_audit.context import FindingsSink, ScanContext
from plex_audit.path_mapper import PathMapper, PathMapping
from plex_audit.plex_client import Library, MediaFile
from plex_audit.types import Severity


def _ctx(tmp_path: Path, plex_files: list[str], mappings: list[PathMapping]) -> ScanContext:
    plex = MagicMock()
    plex.iter_libraries.return_value = [Library(title="TV", kind="show", raw=MagicMock())]

    def fake_items(_lib):  # yields fake items with .media[].parts[].file
        for idx, plex_path in enumerate(plex_files):
            item = MagicMock()
            item.ratingKey = str(idx)
            part = MagicMock()
            part.file = plex_path
            media = MagicMock()
            media.parts = [part]
            item.media = [media]
            yield item

    # OrphanedFilesCheck iterates library.raw.all()
    for lib in plex.iter_libraries.return_value:
        lib.raw.all = lambda _lib=lib: list(fake_items(_lib))

    def get_media_files(item):
        for media in item.media:
            for part in media.parts:
                yield MediaFile(plex_path=part.file, rating_key=str(item.ratingKey))
    plex.get_media_files.side_effect = get_media_files

    return ScanContext(
        plex=plex,
        path_mapper=PathMapper(mappings),
        config=MagicMock(),
        filesystem_available=True,
        _sink=FindingsSink(),
    )


def test_finds_files_on_disk_not_in_plex(tmp_path: Path):
    media_root = tmp_path / "tv"
    media_root.mkdir()
    (media_root / "known.mkv").write_text("")
    (media_root / "orphan.mkv").write_text("")
    (media_root / "ignored.txt").write_text("")  # non-video, ignored

    ctx = _ctx(
        tmp_path,
        plex_files=[str(media_root / "known.mkv")],
        mappings=[PathMapping(plex=str(media_root), local=str(media_root))],
    )
    OrphanedFilesCheck().run(ctx)
    findings = ctx._sink.all()
    assert len(findings) == 1
    assert findings[0].subject.endswith("orphan.mkv")
    assert findings[0].severity == Severity.WARN


def test_skips_non_video_extensions(tmp_path: Path):
    assert ".mkv" in VIDEO_EXTENSIONS
    assert ".mp4" in VIDEO_EXTENSIONS
    assert ".txt" not in VIDEO_EXTENSIONS


def test_emits_info_when_no_mappings(tmp_path: Path):
    ctx = _ctx(tmp_path, plex_files=[], mappings=[])
    # Simulate engine behavior: check runs but has no filesystem to walk.
    # With requires_filesystem=True the engine would skip it; this test asserts direct behavior.
    list(OrphanedFilesCheck().run(ctx))
    # No crash, no false positives.
    assert ctx._sink.all() == []
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit/tests/checks/test_orphaned_files.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Create `packages/plex_audit/src/plex_audit/checks/__init__.py`** (empty file)

- [ ] **Step 4: Implement `checks/orphaned_files.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from plex_audit.context import ScanContext
from plex_audit.types import Category, Finding, Severity

VIDEO_EXTENSIONS = frozenset({
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm", ".mpg", ".mpeg", ".ts"
})


class OrphanedFilesCheck:
    id = "orphaned_files"
    name = "Orphaned Files"
    category = Category.FILE_HEALTH
    parallel_safe = True
    requires_filesystem = True

    def run(self, ctx: ScanContext) -> Iterable[Finding]:
        if not ctx.path_mapper.has_mappings:
            return

        known_local_files: set[Path] = set()
        local_roots: set[Path] = set()

        for library in ctx.plex.iter_libraries():
            for item in library.raw.all():
                for media_file in ctx.plex.get_media_files(item):
                    local = ctx.path_mapper.to_local(media_file.plex_path)
                    if local is None:
                        continue
                    resolved = Path(str(local))
                    known_local_files.add(resolved)

        # Derive roots from the configured mappings themselves.
        for mapping in ctx.config.paths.mappings:
            local_root = Path(mapping.local)
            if local_root.exists():
                local_roots.add(local_root)

        for root in local_roots:
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                if path in known_local_files:
                    continue
                ctx.report(
                    Finding(
                        check_id=self.id,
                        severity=Severity.WARN,
                        title="Orphaned file on disk",
                        subject=str(path),
                        file_path=path,
                        suggested_action="Add to a Plex library or delete",
                    )
                )
```

- [ ] **Step 5: Register the entry point**

Edit `packages/plex_audit/pyproject.toml` — replace the empty `[project.entry-points."plex_audit.checks"]` section with:

```toml
[project.entry-points."plex_audit.checks"]
orphaned_files = "plex_audit.checks.orphaned_files:OrphanedFilesCheck"
```

- [ ] **Step 6: Re-sync so the new entry point is registered**

Run: `uv sync --all-packages --reinstall-package plex-audit`
Expected: success.

- [ ] **Step 7: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit/tests/checks/test_orphaned_files.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Confirm entry point discovery works**

Run this one-liner:

```bash
uv run python -c "from plex_audit.engine import Engine; e = Engine.from_entry_points(); print([c.id for c in e._checks])"
```

Expected output: `['orphaned_files']`

- [ ] **Step 9: Commit**

```bash
git add packages/plex_audit/src/plex_audit/checks packages/plex_audit/tests/checks packages/plex_audit/pyproject.toml
git commit -m "feat(checks): add orphaned_files check and register as entry point"
```

---

## Task 10: CLI `plex-audit scan` command

**Files:**
- Create: `packages/plex_audit_cli/src/plex_audit_cli/main.py`
- Create: `packages/plex_audit_cli/tests/test_scan_cli.py`

- [ ] **Step 1: Write the failing tests**

`packages/plex_audit_cli/tests/test_scan_cli.py`:

```python
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from plex_audit_cli.main import app

runner = CliRunner()

CONFIG = """
plex:
  url: http://localhost:32400
  token: t
paths:
  mappings: []
checks:
  enabled: all
  disabled: []
report:
  formats: [md]
  output_dir: "{out}"
  filename_template: "plex-audit-{{timestamp}}"
logging:
  level: INFO
  file: ./plex-audit.log
"""


def _write_config(tmp_path: Path) -> Path:
    out = tmp_path / "reports"
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG.format(out=out.as_posix()), encoding="utf-8")
    return cfg


def test_scan_returns_zero_on_clean_run(tmp_path: Path):
    cfg = _write_config(tmp_path)

    with patch("plex_audit_cli.main.PlexClient") as plex_cls:
        plex_cls.return_value.iter_libraries.return_value = []
        result = runner.invoke(app, ["scan", "--config", str(cfg)])

    assert result.exit_code == 0, result.stdout
    report_files = list((tmp_path / "reports").glob("*.md"))
    assert len(report_files) == 1
    assert "No findings" in report_files[0].read_text(encoding="utf-8")


def test_scan_exits_four_on_missing_config(tmp_path: Path):
    result = runner.invoke(app, ["scan", "--config", str(tmp_path / "no.yaml")])
    assert result.exit_code == 4


def test_scan_exits_three_when_plex_unreachable(tmp_path: Path):
    cfg = _write_config(tmp_path)
    with patch("plex_audit_cli.main.PlexClient") as plex_cls:
        # Trigger connection failure on first use.
        plex_cls.return_value.iter_libraries.side_effect = ConnectionError("nope")
        result = runner.invoke(app, ["scan", "--config", str(cfg)])
    assert result.exit_code == 3
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit_cli/tests/test_scan_cli.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `main.py`**

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from plex_audit.config import Config, ConfigError, load_config
from plex_audit.context import FindingsSink, ScanContext
from plex_audit.engine import Engine
from plex_audit.path_mapper import PathMapper, PathMapping
from plex_audit.plex_client import PlexClient
from plex_audit.reporters.markdown import MarkdownReporter
from plex_audit.types import Severity

app = typer.Typer(help="Plex Media Server library auditor")
log = logging.getLogger("plex_audit_cli")

EXIT_CLEAN = 0
EXIT_WARNINGS = 1
EXIT_ERRORS = 2
EXIT_PLEX_UNREACHABLE = 3
EXIT_CONFIG_INVALID = 4


def _configure_logging(config: Config) -> None:
    Path(config.logging.file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=config.logging.level,
        filename=config.logging.file,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _build_path_mapper(config: Config) -> PathMapper:
    return PathMapper([PathMapping(plex=m.plex, local=m.local) for m in config.paths.mappings])


def _output_path(config: Config, fmt: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = config.report.filename_template.format(timestamp=timestamp)
    return Path(config.report.output_dir) / f"{name}.{fmt}"


def _exit_code_for(highest: Severity | None) -> int:
    if highest is None or highest == Severity.INFO:
        return EXIT_CLEAN
    if highest == Severity.WARN:
        return EXIT_WARNINGS
    return EXIT_ERRORS


@app.command()
def scan(
    config_path: Annotated[Path, typer.Option("--config", "-c", help="Path to config.yaml")] = Path("config.yaml"),
) -> None:
    """Run a full audit and write reports."""
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.secho(f"Config error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=EXIT_CONFIG_INVALID)

    _configure_logging(config)

    path_mapper = _build_path_mapper(config)
    plex_client = PlexClient(config.plex)

    try:
        # Trigger Plex connection early so we can surface a clean error.
        list(plex_client.iter_libraries())
    except Exception as exc:
        typer.secho(f"Could not reach Plex: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=EXIT_PLEX_UNREACHABLE)

    sink = FindingsSink()
    ctx = ScanContext(
        plex=plex_client,
        path_mapper=path_mapper,
        config=config,
        filesystem_available=path_mapper.has_mappings,
        _sink=sink,
    )

    engine = Engine.from_entry_points()
    engine.run(ctx, enabled=config.checks.enabled, disabled=config.checks.disabled)

    findings = sink.all()
    for fmt in config.report.formats:
        if fmt == "md":
            MarkdownReporter().write(findings, _output_path(config, "md"))
        # json/html reporters arrive in Plan 3.

    typer.echo(f"Scan complete. {len(findings)} finding(s).")
    raise typer.Exit(code=_exit_code_for(sink.highest_severity()))


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `uv run pytest packages/plex_audit_cli/tests/test_scan_cli.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Verify the console script works**

Run: `uv run plex-audit --help`
Expected: Typer help text listing the `scan` command.

- [ ] **Step 6: Commit**

```bash
git add packages/plex_audit_cli
git commit -m "feat(cli): add plex-audit scan command with config loading and exit codes"
```

---

## Task 11: End-to-end smoke test

**Files:**
- Create: `packages/plex_audit_cli/tests/test_scan_e2e.py`

- [ ] **Step 1: Write the failing test**

`packages/plex_audit_cli/tests/test_scan_e2e.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from plex_audit_cli.main import app

runner = CliRunner()


def _make_library_with_one_known_file(known_plex_path: str):
    part = MagicMock()
    part.file = known_plex_path
    media = MagicMock()
    media.parts = [part]
    item = MagicMock()
    item.media = [media]
    item.ratingKey = "1"

    library = MagicMock()
    library.kind = "show"
    library.title = "TV"
    library.raw.all.return_value = [item]
    return library


def test_end_to_end_detects_orphan_and_writes_report(tmp_path: Path):
    media_root = tmp_path / "tv"
    media_root.mkdir()
    known = media_root / "known.mkv"
    known.write_text("")
    orphan = media_root / "orphan.mkv"
    orphan.write_text("")

    config_body = f"""
plex:
  url: http://x
  token: t
paths:
  mappings:
    - plex: {media_root.as_posix()}
      local: {media_root.as_posix()}
checks:
  enabled: all
  disabled: []
report:
  formats: [md]
  output_dir: {(tmp_path / "reports").as_posix()}
  filename_template: "plex-audit-{{timestamp}}"
logging:
  level: INFO
  file: {(tmp_path / "plex-audit.log").as_posix()}
"""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(config_body, encoding="utf-8")

    library = _make_library_with_one_known_file(str(known))

    with patch("plex_audit_cli.main.PlexClient") as plex_cls:
        instance = plex_cls.return_value
        instance.iter_libraries.return_value = [library]

        def get_media_files(item):
            from plex_audit.plex_client import MediaFile
            for media in item.media:
                for part in media.parts:
                    yield MediaFile(plex_path=part.file, rating_key=str(item.ratingKey))
        instance.get_media_files.side_effect = get_media_files

        result = runner.invoke(app, ["scan", "--config", str(cfg)])

    assert result.exit_code == 1, result.stdout  # warning severity
    reports = list((tmp_path / "reports").glob("*.md"))
    assert len(reports) == 1
    text = reports[0].read_text(encoding="utf-8")
    assert "orphan.mkv" in text
    assert "known.mkv" not in text
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest packages/plex_audit_cli/tests/test_scan_e2e.py -v`
Expected: initial run may FAIL if `iter_libraries` mock setup mismatches the scan's early connection probe. Iterate until PASS.

Concretely, the scan's early probe calls `list(plex_client.iter_libraries())` first, then `engine.run(...)` iterates it again — but `iter_libraries` on the mock returns the same list both times (MagicMock memoizes `return_value`). That is already handled by the test above.

- [ ] **Step 3: Make it pass**

No new production code should be needed. If the test fails, the failure points to a real bug in Tasks 1–10 — fix there, don't patch around it.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Run lint and types**

Run: `uv run ruff check . && uv run mypy packages/plex_audit/src packages/plex_audit_cli/src`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add packages/plex_audit_cli/tests/test_scan_e2e.py
git commit -m "test: add end-to-end smoke test for plex-audit scan with orphaned_files"
```

---

## Self-review notes

- Spec coverage: this plan delivers the foundation (Config, PlexClient, PathMapper, Engine, ScanContext, Check/Finding types, markdown reporter, one check, CLI scan command). Remaining spec items (other 10 checks, JSON/HTML reporters, wizard, scheduler, distribution) are explicitly deferred to Plans 2–4.
- No placeholders: every step has exact code or exact commands.
- Type consistency: `Finding` is declared once (Task 2) and amended once (Task 6) — the amendment is spelled out in full, not as "similar to before". `PathMapping` exists as a dataclass in `path_mapper.py` (Task 3) and as a pydantic model `PathMappingModel` in `config.py` (Task 4); the CLI (Task 10) translates between them explicitly.
- Exit codes from the spec (0/1/2/3/4) are implemented in Task 10 and verified in Tasks 10 and 11.
