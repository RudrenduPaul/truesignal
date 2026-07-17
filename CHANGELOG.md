# Changelog

All notable changes to this project are documented in this file. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

## [Python 0.1.0] - 2026-07-16

### Added

- `truesignal` on PyPI: a genuine, independent Python port of the npm package (not a wrapper
  around the Node binary) -- the same five connectors (CISA-KEV, Cloudflare Radar, Reddit,
  Telegram, GDELT), the same provenance-stamping guarantee, and the same `init`/`feed`/`verify`
  CLI surface, implemented as real Python (`python/src/truesignal/`) with zero third-party
  runtime dependencies (stdlib `urllib` for HTTP, stdlib `argparse` for the CLI).
- Full pytest suite (`python/tests/`, 101 tests) including a direct port of the TypeScript
  no-fabrication guarantee suite (`test_no_fabrication.py`) covering every connector's live,
  fallback, and empty-cache-failure paths, plus a static scan of every connector source file for
  forbidden patterns (`random.random()`, a fake-data library, `datetime.now()` used to construct
  an item's timestamp).
- `docs/getting-started.md`, `docs/concepts.md`, `docs/integrations/ci.md` -- shared documentation
  covering both the npm and PyPI distributions.
- `python/examples/` -- three numbered, runnable examples against the real Python library API.
- `SECURITY.md` -- vulnerability reporting policy for both distributions.

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
