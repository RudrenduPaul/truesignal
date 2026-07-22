# truesignal (Python)

A provenance-first OSINT/security intelligence feed. Every item ships a real
source URL, a real upstream timestamp, and an explicit `live`/`fallback`
flag -- never a fabricated or silently-replayed data point.

[![PyPI version](https://img.shields.io/pypi/v/truesignal-cli.svg)](https://pypi.org/project/truesignal-cli/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/RudrenduPaul/truesignal/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/truesignal-cli.svg)](https://pypi.org/project/truesignal-cli/)
[![CI](https://github.com/RudrenduPaul/truesignal/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/truesignal/actions/workflows/ci.yml)

## Why this exists

Personal OSINT/security feeds are easy to build and easy to get wrong in one
specific way: silently showing stale or synthetic data as if it were
current. TrueSignal's answer is structural, not a documentation promise --
every connector's failure path is enforced by a dedicated test suite to
return either a real cached item honestly labeled `fallback` with its real
age, or nothing at all. This package is the Python distribution -- a
genuine, independent port of the npm package, not a wrapper around the
Node binary.

## Install

```bash
pip install truesignal-cli
```

or with [uv](https://docs.astral.sh/uv/):

```bash
uv add truesignal-cli
```

No separate install step, no external binary to fetch. The complementary
JS/TS distribution installs the same way on the npm side:
`npm install -g truesignal-cli` (or `npx truesignal-cli init` to run it once
without installing) -- see the
[project README](https://github.com/RudrenduPaul/truesignal#readme) for
that package. Both are first-class, maintained together; neither is
deprecated in favor of the other.

## Quickstart

```bash
truesignal init
truesignal feed
```

`init` reports which connectors are ready right now -- CISA-KEV and GDELT
need no configuration -- and which environment variables are still missing
for the rest (Cloudflare Radar, Reddit, Telegram). `feed` pulls from every
configured connector.

Or call the library directly (the agent-native path):

```python
from truesignal import ALL_CONNECTORS

for connector in ALL_CONNECTORS:
    if connector.requires_config and not connector.is_configured():
        continue
    for item in connector.fetch_items():
        print(item.status, item.source, item.url)
```

## How it works

```
connector.fetch_items()
   -> fetch_with_fallback(source, fetch_live)
        -> upstream API call succeeds -> stamp_live() -> write_cache() -> real "live" items
        -> upstream API call fails    -> read_cache() -> stamp_fallback() -> real "fallback"
                                          items with an honest fallback_age_seconds, or []
                                          if nothing has ever been cached
```

Every connector implements the same `Connector` interface
(`truesignal/types.py`) and calls `fetch_with_fallback` instead of touching
the network directly -- that single function is what gives every connector
its live/fallback/nothing guarantee. See
[docs/concepts.md](https://github.com/RudrenduPaul/truesignal/blob/main/docs/concepts.md)
for the full data model and what each of the five connectors actually
returns.

## No-fabrication guarantee

Every connector's live, fallback, and empty-cache-failure path is covered
by a dedicated pytest suite (`tests/test_no_fabrication.py`), ported
directly from the TypeScript suite's `no-fabrication.test.ts`: it proves,
for every connector, that a failed upstream fetch never produces
synthetic, randomized, or silently-relabeled-as-current data -- only a real
cached fallback item with an honest age, or nothing. A companion static
check scans every connector source file in `src/truesignal/connectors/`
for forbidden patterns (`random.random()`, a fake-data library,
`datetime.now()` used to construct an item's timestamp).

## CLI command reference

```
usage: truesignal [-h] [--version] {init,feed,verify} ...

Commands:
  init [--json]                     Check which connectors are ready right now.
  feed [--source NAME] [--json]     Pull the current feed from every configured
                                     connector, or one connector with --source.
  verify <item-id> [--json]         Re-fetch the source named in <item-id> and
                                     confirm its current provenance.
```

Exit codes: `0` success, `1` general error, `2` no connectors configured,
`3` network error (a configured connector's fetch failed with no fallback
data), `4` a malformed or unknown `verify` item id -- documented in full in
[docs/concepts.md](https://github.com/RudrenduPaul/truesignal/blob/main/docs/concepts.md).

## Security

No connector ever `eval()`s, `exec()`s, or dynamically imports anything
read from an upstream response -- responses are only ever parsed as JSON
and mapped into typed fields. Credentials are read only from real
environment variables (`CLOUDFLARE_RADAR_API_TOKEN`, `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`) -- never accepted as a CLI
flag, never auto-loaded from a `.env` file. To report a vulnerability, see
[SECURITY.md](https://github.com/RudrenduPaul/truesignal/blob/main/SECURITY.md).
**Honest note**: this project does not currently publish SLSA provenance,
Sigstore signatures, or an SBOM, and has no OpenSSF Scorecard badge set up
-- none of that infrastructure exists yet for either distribution, so it
isn't claimed here.

## FAQ

**What does this do?**
Pulls OSINT and security-relevant items (CVEs, threat intel, security news) from five official
APIs -- CISA-KEV, Cloudflare Radar, Reddit, Telegram, GDELT -- and stamps every item with a real
source URL, a real upstream timestamp, and an explicit `live`/`fallback` label, so you never see
fabricated or silently-stale data presented as current.

**How is this PyPI package different from the npm one, if at all?**
It isn't a wrapper around the Node binary -- it's a genuine, independent Python port with the same
five connectors, the same `fetch_with_fallback` provenance guarantee, and the same `init`/`feed`/
`verify` CLI surface. Both distributions are first-class and maintained together; neither is
deprecated in favor of the other, so pick whichever fits your toolchain.

**Does this need an API key?**
Not to start. CISA-KEV and GDELT work with zero configuration. Cloudflare Radar, Reddit, and
Telegram each need a free developer key or token, read only from environment variables
(`CLOUDFLARE_RADAR_API_TOKEN`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`) --
`truesignal init` tells you exactly which ones are still missing.

**Is it safe to run?**
No connector `eval()`s, `exec()`s, or dynamically imports anything read from an upstream response
-- responses are only ever parsed as JSON and mapped into typed fields. Credentials are never
accepted as a CLI flag and never auto-loaded from a `.env` file. See the Security section above
for the current caveat on SLSA/Sigstore/SBOM/Scorecard coverage.

**What happens if a source goes down?**
The connector returns real cached data explicitly labeled `fallback` (with its exact real age in
`fallback_age_seconds`), or nothing at all -- never invented data, and never old data silently
relabeled as current. That guarantee is enforced by `tests/test_no_fabrication.py` for every one
of the 5 connectors.

## Contributing

See [CONTRIBUTING.md](https://github.com/RudrenduPaul/truesignal/blob/main/CONTRIBUTING.md)
for the full guide, covering both the TypeScript and Python codebases.

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT, see [LICENSE](https://github.com/RudrenduPaul/truesignal/blob/main/LICENSE).

