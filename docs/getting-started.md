# Getting started

TrueSignal pulls OSINT and security-relevant items from five official APIs
(CISA-KEV, Cloudflare Radar, Reddit, Telegram, GDELT) and stamps every item
with a real source URL, a real upstream timestamp, and an explicit
`live`/`fallback` label. It ships as two independent, equally first-class
packages: an npm package (`truesignal-cli`, JavaScript/TypeScript) and a
PyPI package (`truesignal`, Python). Pick whichever fits your toolchain, or
install both.

## Install

**npm (JS/TS CLI):**

```bash
npx truesignal-cli init
```

`truesignal-cli` is published on npm. To build from source instead:

```bash
git clone https://github.com/RudrenduPaul/truesignal.git && cd truesignal && npm install && npm run build && node dist/cli.js init
```

**pip (Python library + CLI):**

```bash
pip install truesignal
```

Neither install pulls anything beyond the connector's own upstream API call
at fetch time -- no separate scanner binary, no background service. Two of
the five connectors (CISA-KEV, GDELT) need zero configuration at all.

## Your first run

```bash
truesignal init
```

Real output (Python CLI shown; the npm CLI's output is line-for-line
identical except for how it's invoked):

```
truesignal connector status:

  [ready]        CISA Known Exploited Vulnerabilities (cisa-kev) -- no configuration needed
  [not configured] Cloudflare Radar (cloudflare-radar) -- set CLOUDFLARE_RADAR_API_TOKEN
  [not configured] Reddit (reddit) -- set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
  [not configured] Telegram (telegram) -- set TELEGRAM_BOT_TOKEN
  [ready]        GDELT (gdelt) -- no configuration needed

2/5 connectors ready.
Set the missing environment variables above to enable the rest. See .env.example.
Next: run "truesignal feed" to see your feed now.
```

Then pull the feed from the two zero-config sources:

```bash
truesignal feed --source cisa-kev
```

Real, unedited capture from this Python port, against the live CISA-KEV
catalog:

```
[live] cisa-kev: CVE-2026-58644: Microsoft SharePoint Deserialization of Untrusted Data Vulnerability -- https://nvd.nist.gov/vuln/detail/CVE-2026-58644 -- 1d ago
[live] cisa-kev: CVE-2026-25089: Fortinet FortiSandbox OS Command Injection Vulnerability -- https://nvd.nist.gov/vuln/detail/CVE-2026-25089 -- 1d ago
```

To enable the other three connectors (Cloudflare Radar, Reddit, Telegram),
copy `.env.example` to `.env`, fill in real free credentials, then export
them into your shell -- truesignal doesn't auto-load `.env` files:

```bash
set -a && source .env && set +a
```

## Using the library instead of the CLI

Both packages export the connector layer directly, for an agent framework
or script that wants to call TrueSignal in-process instead of shelling out
to a CLI binary.

**TypeScript:**

```ts
import { allConnectors } from 'truesignal-cli';

for (const connector of allConnectors) {
  if (connector.requiresConfig && !connector.isConfigured()) continue;
  for (const item of await connector.fetchItems()) {
    console.log(item.status, item.source, item.url);
  }
}
```

**Python:**

```python
from truesignal import ALL_CONNECTORS

for connector in ALL_CONNECTORS:
    if connector.requires_config and not connector.is_configured():
        continue
    for item in connector.fetch_items():
        print(item.status, item.source, item.url)
```

Both return the same `FeedItem`/`FeedItem` shape (`id`, `source`, `title`,
`url`, `timestamp`, `status`, and `fallback_age_seconds`/
`fallbackAgeSeconds` when `status` is `fallback`) -- field names are
snake_case in Python and camelCase in TypeScript, each following its own
language's convention. See [concepts.md](./concepts.md) for the full data
model.

## Next steps

- [concepts.md](./concepts.md) -- what "provenance-first" means concretely,
  what each of the five connectors actually returns, and the exit-code
  contract.
- [integrations/ci.md](./integrations/ci.md) -- using TrueSignal as a
  scheduled CI job (a security-feed digest, a CI gate on new
  CISA-KEV entries, etc).
- The [project README](../README.md) for the full comparison table and
  the reasoning behind the no-fabrication guarantee.
