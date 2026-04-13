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
    formats: list[Literal["md", "json", "html"]] = Field(default=["md"])
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
