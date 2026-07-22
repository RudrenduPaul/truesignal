# CI integrations

TrueSignal is a pull tool, not a gate -- it doesn't fail a build the way a
scanner does. The common CI use case is a scheduled job that posts a
digest (new CISA-KEV entries, security-relevant GDELT coverage) or, for a
security team, a step that fails a pipeline when a specific
`verify <item-id>` check no longer resolves live. Both packages support
the same `--json` output contract, so pick whichever matches your
pipeline's existing toolchain.

## GitHub Actions -- scheduled CISA-KEV digest (Python CLI)

```yaml
name: TrueSignal CISA-KEV digest
on:
  schedule:
    - cron: '0 13 * * *'
  workflow_dispatch:

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install truesignal
      - name: Pull today's CISA-KEV feed
        run: truesignal feed --source cisa-kev --json > cisa-kev.json
      - uses: actions/upload-artifact@v4
        with:
          name: cisa-kev-digest
          path: cisa-kev.json
```

## GitHub Actions -- scheduled CISA-KEV digest (npm CLI)

```yaml
name: TrueSignal CISA-KEV digest
on:
  schedule:
    - cron: '0 13 * * *'
  workflow_dispatch:

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npx --yes truesignal-cli feed --source cisa-kev --json > cisa-kev.json
      - uses: actions/upload-artifact@v4
        with:
          name: cisa-kev-digest
          path: cisa-kev.json
```

## Gating on a specific item still being live

`truesignal verify <item-id>` exits `0` when the item resolves to real,
live or fallback provenance, `1` when it re-fetched successfully but the
item is gone, and `3` on a network error re-fetching it -- a plain shell
step can gate a job on that directly:

```yaml
- name: Confirm a specific CVE is still tracked live
  run: |
    pip install truesignal
    truesignal verify cisa-kev:CVE-2026-12345
```

## Configuring the paid/free-key connectors in CI

Cloudflare Radar, Reddit, and Telegram each need a credential passed as a
real environment variable -- never a CLI flag, and truesignal never
auto-loads a `.env` file. In GitHub Actions, store the value as a repository
secret and wire it in via `env:`:

```yaml
- run: truesignal feed --source cloudflare-radar
  env:
    CLOUDFLARE_RADAR_API_TOKEN: ${{ secrets.CLOUDFLARE_RADAR_API_TOKEN }}
```

## Choosing what to automate

`cisa-kev` and `gdelt` need no credentials, so they're the lowest-friction
connectors to run on a schedule. GDELT's public API enforces a documented
rate limit (roughly one request per 5 seconds per client) -- a scheduled
job calling it more often than that will see the connector correctly fall
back to cached data (or return nothing, honestly, if nothing has been
cached yet) rather than fail the whole job.
