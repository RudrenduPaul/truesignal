# Contributing to truesignal

Thanks for looking at truesignal. This project has one rule that overrides everything else:
**never let a connector fabricate, randomize, or silently replay stale data as if it were live.**
Every other guideline below exists to support that one.

## Getting set up

```bash
git clone https://github.com/RudrenduPaul/truesignal.git
cd truesignal
npm install
npm run build
npm test
```

CISA-KEV and GDELT need no API keys, so `npm test` and local development work with zero setup.
To exercise the other three connectors locally, copy `.env.example` to `.env` and fill in real
(free) credentials for the sources you want to test against.

## Before you open a pull request

Run all of these locally; CI runs the same checks and will fail the same way if you skip one:

```bash
npx eslint .
npx prettier --check .
npx tsc --noEmit --strict
npx vitest run --coverage
npm audit --audit-level=high
```

- Coverage must stay at or above 80% overall, and 95%+ on `src/truesignal/provenance/`.
- Zero `@ts-ignore` or `@ts-expect-error` without a comment explaining exactly why it's safe.
- No `Math.random()`, no third-party fake-data generator, and no `new Date().toISOString()` used
  to construct an item's `timestamp` field, anywhere in `src/truesignal/connectors/`. A dedicated
  test (`src/truesignal/provenance/no-fabrication.test.ts`) enforces this both by behavior and by
  scanning connector source files directly -- it will fail your PR if either check trips.

## Adding a new connector

This is the extensibility point this project is built around. Every source lives behind the same
`Connector` interface (`src/truesignal/types.ts`), so adding one is a scoped, additive change:

1. **Create `src/truesignal/connectors/<your-source>.ts`.** Look at `src/truesignal/connectors/gdelt.ts`
   for the simplest example (no auth) or `src/truesignal/connectors/reddit.ts` for one that needs
   OAuth credentials.
2. **Implement the `Connector` interface:**
   - `name` -- the machine-readable id used as the `--source` flag value and as the prefix of
     every item's `id` (`<name>:<native-id>`).
   - `label` -- a human-readable name for `truesignal init` output.
   - `requiresConfig` / `configEnvVars` -- if your source needs a key or token, read it only from
     `process.env`. Never hardcode a credential, and never accept one as a CLI flag (flags show up
     in shell history and process lists).
   - `isConfigured()` -- return `true` only when every required env var is present and non-empty.
   - `fetchItems()` -- do the real network call here, but never call it directly. Wrap it with
     `fetchWithFallback(name, fetchLiveFn)` from `src/truesignal/provenance/stamp.ts`. That
     function is what gives you the live/fallback/nothing guarantee for free -- you only need to
     write the part that turns a real upstream response into `UnstampedItem[]`.
3. **Map upstream fields honestly.** `url` must be a real, dereferenceable link to the specific
   item (not a generic homepage). `timestamp` must come from a real field the upstream API
   returned (not `new Date()`). If the upstream response doesn't give you a real per-item URL or
   timestamp, that item should be skipped, not included with an invented value -- see how
   `src/truesignal/connectors/telegram.ts` skips messages from chats with no public username
   rather than fabricating a link.
4. **Register it** in `src/truesignal/connectors/index.ts`'s `allConnectors` array. Nothing else in
   the CLI or provenance layer needs to change.
5. **Write tests** covering: a successful live fetch, a failure with a prior cache (asserts
   `status: 'fallback'` and a real `fallbackAgeSeconds`), and a failure with no prior cache
   (asserts an empty array). Follow the pattern in any existing `*.test.ts` file next to your
   connector, and add your connector to the shared table in
   `src/truesignal/provenance/no-fabrication.test.ts`.
6. **Only use the source's official API.** If a source has no free/official API, or its official
   API can't get you what you need without violating its terms of service, that's a reason not to
   add it this way -- open an issue to discuss instead of adding a scraping fallback.

## Reporting a bug

Please include: the exact command you ran, the full output (redact any real API keys), your
Node.js version, and whether the bug is about a specific connector or the CLI itself. If you
believe you've found a case where truesignal shows fabricated or mislabeled data, please say so
explicitly in the title -- that class of bug gets fixed first.

## Code style

Formatting is enforced by Prettier and linting by ESLint; run `npm run format:write` before
committing if `prettier --check` complains. There's no separate style guide beyond what those
tools already enforce.
