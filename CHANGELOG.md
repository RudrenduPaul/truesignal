# Changelog

All notable changes to this project are documented in this file. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-07-15

### Added

- Initial release: `truesignal-cli`, a provenance-first OSINT/security intelligence feed.
- Five source connectors behind a common `Connector` interface:
  CISA-KEV, Cloudflare Radar, Reddit (official OAuth API), Telegram (official Bot API), GDELT.
- Provenance-stamping layer (`src/truesignal/provenance/`): every feed item is tagged `live` or
  `fallback`, with a real cached-data age whenever it falls back, and never a fabricated or
  silently-replayed data point.
- CLI subcommands: `truesignal init`, `truesignal feed [--source <name>] [--json]`,
  `truesignal verify <item-id> [--json]`.
- Test suite (Vitest) including a dedicated no-fabrication guarantee test covering every
  connector's live, fallback, and empty-cache failure paths.
- CI pipeline: lint, type-check, test with coverage, dependency audit.
