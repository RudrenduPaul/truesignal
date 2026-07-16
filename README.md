# truesignal

A personal intelligence feed that never fabricates a data point.

```bash
npx truesignal-cli init
```

> This README is an early placeholder covering install and usage. A fuller version with
> measured benchmarks against comparable tools ships in a later pass of this project.

## What it does

truesignal pulls from five OSINT/security sources and stamps every item with a real source URL,
a real timestamp, and an explicit `live` or `fallback` status. If a source is unreachable, you get
honestly-labeled cached data, or nothing. Nothing is ever invented.

```bash
npx truesignal-cli init
npx truesignal-cli feed
```

```
[live] cisa-kev: CVE-2026-XXXXX: Sample vulnerability -- https://nvd.nist.gov/vuln/detail/CVE-2026-XXXXX -- 2m ago
[fallback, 3h old] reddit: Sample thread title -- https://reddit.com/r/netsec/... -- 3h ago
```

## Install

```bash
npx truesignal-cli init
```

or, for repeat use:

```bash
npm install -g truesignal-cli
truesignal init
```

Requires Node.js 18.17 or later.

## Sources (v0.1)

| Source                                          | Needs a key? | Env var(s)                                 |
| ----------------------------------------------- | ------------ | ------------------------------------------ |
| CISA Known Exploited Vulnerabilities (CISA-KEV) | No           | --                                         |
| GDELT                                           | No           | --                                         |
| Cloudflare Radar                                | Yes, free    | `CLOUDFLARE_RADAR_API_TOKEN`               |
| Reddit (official OAuth API)                     | Yes, free    | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` |
| Telegram (official Bot API)                     | Yes, free    | `TELEGRAM_BOT_TOKEN`                       |

CISA-KEV and GDELT work with zero configuration. Copy `.env.example` to `.env` and fill in real
(free) credentials to enable the other three -- see that file for where to get each one. truesignal
does not auto-load `.env`; export the values into your shell first, e.g.
`set -a && source .env && set +a`.

## CLI reference

### `truesignal init`

Checks which connectors are ready to use and which environment variables are still missing for
the rest.

```bash
truesignal init
truesignal init --json
```

Exit code `0` if at least one connector is usable, `2` if none are (should not happen -- CISA-KEV
and GDELT need no configuration).

### `truesignal feed [--source <name>] [--json]`

Pulls the current feed from every configured connector, or one connector with `--source`.

```bash
truesignal feed
truesignal feed --source cisa-kev --json
```

Exit codes: `0` success, `2` no connectors configured to run, `3` every configured connector's
fetch failed with no data to show.

### `truesignal verify <item-id> [--json]`

Re-fetches the source named in `<item-id>` (format `<source>:<native-id>`, e.g.
`cisa-kev:CVE-2026-12345`) and confirms whether that item still resolves to real, live
provenance, has fallen back to cached data, or can no longer be found.

```bash
truesignal verify cisa-kev:CVE-2026-12345 --json
```

Exit codes: `0` found and live/fallback, `1` re-fetched successfully but the item is gone, `2` the
connector isn't configured, `3` the re-fetch failed, `4` the item id is malformed or names an
unknown source.

## Self-host

Everything runs on your machine using your own API keys. No account, no telemetry by default.

## License

MIT. See [LICENSE](./LICENSE).
