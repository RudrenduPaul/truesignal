# Concepts

## The provenance-stamping pipeline

Both the npm and PyPI packages run the same pipeline (TypeScript:
`src/truesignal/provenance/stamp.ts`; Python: `truesignal/provenance/stamp.py`):

```
connector.fetch_items() / connector.fetchItems()
        |
        v
fetch_with_fallback(source, fetch_live)  /  fetchWithFallback(source, fetchLive)
        |
        +-- fetch_live() succeeds --> stamp_live()     --> write_cache() --> real "live" items
        |
        +-- fetch_live() raises/throws --> read_cache(source)
                                                |
                                                +-- a real cache entry exists --> stamp_fallback()
                                                |     --> real "fallback" items, each carrying an
                                                |         honest fallback_age_seconds / fallbackAgeSeconds
                                                |
                                                +-- no cache entry exists --> [] (empty, never invented)
```

This is the entire product claim, enforced in code rather than only in
documentation: a connector's failure path can only produce a real cached
item honestly labeled `fallback`, or nothing. There is no third path where
data is invented, randomized, or a stale item is silently relabeled as
current.

## The FeedItem shape

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | `"{source}:{native-id}"`, e.g. `cisa-kev:CVE-2026-12345` |
| `source` | string | The connector name, e.g. `cisa-kev` |
| `title` | string | Human-readable title |
| `url` | string | A real, dereferenceable link to the specific upstream item -- never a generic homepage |
| `timestamp` | string | A real ISO-8601 instant from the upstream source, never `new Date()`/`datetime.now()` |
| `status` | `"live"` \| `"fallback"` | Whether this item came from a fetch just now, or cached data |
| `fallback_age_seconds` / `fallbackAgeSeconds` | integer, optional | Present only when `status` is `fallback`: real seconds since the item was last fetched live |
| `summary` | string, optional | Short human-readable context, when the upstream source provides one |

Python field names are snake_case (`fallback_age_seconds`); TypeScript
field names are camelCase (`fallbackAgeSeconds`) -- each following its own
language's convention. Everything else about the shape is identical.

## The five connectors

Each connector implements one shared interface (`Connector` in
`types.ts`/`types.py`): `name`, `label`, `requires_config`/`requiresConfig`,
`config_env_vars`/`configEnvVars`, `is_configured()`/`isConfigured()`, and
`fetch_items()`/`fetchItems()`.

### CISA Known Exploited Vulnerabilities (`cisa-kev`)

No configuration needed. Pulls the public CISA-KEV JSON feed
(`https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`),
sorts by `dateAdded` descending, and returns up to 25 of the most recently
added vulnerabilities. Each item links to the CVE's NVD detail page.

### Cloudflare Radar (`cloudflare-radar`)

Requires `CLOUDFLARE_RADAR_API_TOKEN` (a free Cloudflare API token with
Radar read scope). Pulls recent global traffic anomalies from the official
Radar API (`/client/v4/radar/traffic_anomalies`) and links each item to its
Radar anomaly detail page.

### Reddit (`reddit`)

Requires `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` (a free Reddit
developer app, script or web app type). Uses Reddit's official OAuth API
(application-only `client_credentials` grant) to pull new posts from a
security/OSINT-relevant subreddit -- `netsec` by default, overridable via
`REDDIT_SUBREDDIT`. Never scrapes the unauthenticated `.json` endpoints,
which would violate Reddit's API terms of service.

### Telegram (`telegram`)

Requires `TELEGRAM_BOT_TOKEN` (a free bot token from
[@BotFather](https://core.telegram.org/bots#how-do-i-create-a-bot)). Uses
the official Bot API's `getUpdates` long-polling method. A real API
constraint, not a workaround: the Bot API only surfaces updates for chats
the bot has been added to as a member/admin. Posts from a chat with no
public `@username` are skipped rather than linked with a fabricated URL --
every item this connector emits has a real, dereferenceable `t.me` link.

### GDELT (`gdelt`)

No configuration needed. Pulls recent OSINT/security-relevant news coverage
from the GDELT 2.0 DOC API
(`https://api.gdeltproject.org/api/v2/doc/doc`), filtered to English-language
articles matching `(cyberattack OR vulnerability OR "data breach")`. GDELT's
public API enforces a documented rate limit (roughly one request per 5
seconds per client); a request made too soon after a prior one returns a
non-JSON rate-limit notice, which this connector treats as a failed live
fetch -- exactly the case `fetch_with_fallback` exists to handle honestly.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | General/unexpected error (e.g. `feed --source` named an unknown connector) |
| `2` | No connectors configured to run for this command |
| `3` | A configured connector's fetch failed with no fallback data to show |
| `4` | `verify <item-id>` was given an id that doesn't parse or names an unknown source |

## Extending: adding a new connector

Every source lives behind the same interface, so adding one is a scoped,
additive change in both codebases -- see
[CONTRIBUTING.md](../CONTRIBUTING.md#adding-a-new-connector) for the exact
steps. The core rule that governs every connector, old or new: `url` must
be a real, dereferenceable link to the specific item, and `timestamp` must
come from a real field the upstream API returned. If the upstream response
doesn't provide a real per-item URL or timestamp, that item is skipped, not
included with an invented value.
