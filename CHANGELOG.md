# Changelog

## [0.2.0] - 2026-04-13

### Added
- add Dockerfile and entrypoint
- add changelog generator and seed CHANGELOG.md
- add conventional-commits version bump script
- add schedule --show with cron and schtasks templates
- add plex-audit init wizard
- dispatch to markdown/json/html reporters based on config
- add HTML reporter with severity-colored sortable tables
- add JSON reporter
- add near_duplicates check with optional edition-stripping
- add duplicates check for items with multiple file variants
- add opt-in ffprobe_integrity check
- add quality_threshold check with configurable res/bitrate/codec
- add missing_files check
- add match_confidence check
- add missing_artwork check
- add unmatched_items check
- add missing_episodes check
- add plex-audit scan command with config loading and exit codes
- add orphaned_files check and register as entry point
- add markdown reporter with severity sections
- add Engine with entry-point discovery, filtering, parallel execution, and crash isolation
- add ScanContext and FindingsSink with dedup and severity-sorted output
- add PlexClient wrapper with library cache and MediaFile extraction
- add pydantic Config with YAML + env + override precedence
- add PathMapper with longest-prefix matching
- add Severity, Category, Finding, Check types

### Fixed
- use AUTO_MERGE_TOKEN PAT to push version bumps past branch protection
- use root commit as fallback when no tags exist
- disable all checks in clean-scan test to survive growing check set
- make FindingsSink thread-safe and log plugin load tracebacks

All notable user-facing changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project adheres to [Semantic Versioning](https://semver.org/).
