# Security Policy

TrueSignal's whole product claim is that every item it shows you is either
real, live data or honestly-labeled real cached data -- never invented. A
vulnerability that lets that guarantee be silently violated (a connector
made to fabricate an item, a cache file made to inject a synthetic item
that then gets served as `fallback`, or credential material leaking into
logs or cached files) is taken seriously and handled as a priority.

## Supported versions

| Package | Version | Supported |
| --- | --- | --- |
| `truesignal-cli` (npm) | 0.1.x | Yes |
| `truesignal` (PyPI) | 0.1.x | Yes |

Both distributions are pre-1.0 and under active development. Security fixes
land on the latest `0.1.x` release of each; there is no older supported
line to backport to yet.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Report it privately via
[GitHub Security Advisories](https://github.com/RudrenduPaul/truesignal/security/advisories/new)
for this repository. Include:

- Which distribution is affected (npm package, PyPI package, or both).
- A minimal reproduction: the connector involved, the upstream response
  shape that triggers the issue (or a description of it), and the
  command/library call.
- What you expected TrueSignal to do, and what it actually did.
- Your assessment of impact -- e.g. "a crafted upstream response causes a
  connector to emit an item with a fabricated URL or timestamp" is a
  direct violation of this project's no-fabrication guarantee and should
  be reported as such.

## What counts as in scope

- Any code path where a connector emits a `FeedItem` whose `url` or
  `timestamp` did not come directly from a real upstream API response --
  the no-fabrication guarantee this whole project exists to enforce.
- Any path where the local on-disk cache (`~/.truesignal/cache/*.json`) is
  read in a way that lets a corrupted or attacker-controlled cache file be
  served as if it were genuine previously-fetched data, rather than being
  rejected as "no cache" per the documented contract.
- Any code path where a credential (`CLOUDFLARE_RADAR_API_TOKEN`,
  `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`) is
  written to a log, an error message, or the on-disk cache.
- Any use of `eval()`/`exec()` (Python) or dynamic code evaluation
  (TypeScript) on content read from an upstream API response or the local
  cache file.

## What is out of scope

- Upstream API outages, rate limits, or shape changes in CISA-KEV,
  Cloudflare Radar, Reddit, Telegram, or GDELT themselves -- report those
  to the respective service, not here. TrueSignal's job in that situation
  is only to fail honestly (fallback or empty), which is covered by the
  no-fabrication guarantee above.
- Vulnerabilities in Reddit's, Telegram's, Cloudflare's, CISA's, or
  GDELT's own APIs -- report those to the respective vendor.

## Response

We aim to acknowledge a report within 5 business days and to have a fix or
a mitigation plan within 30 days for a confirmed, in-scope vulnerability.
Credit is given in the release notes unless you ask to remain anonymous.
