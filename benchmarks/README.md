# Benchmarks

This directory holds reproducible benchmarks for truesignal. Every number in the main
[README](../README.md)'s comparison table traces back to one of the commands below -- no
benchmark claim is ever stated without a command whose output reproduces it.

To add a new benchmark, drop a runnable `.ts` file in this directory that prints its result to
stdout, and document the exact command to reproduce it here.

## No-fabrication guarantee (the core product claim)

The single most important test in this repo. It proves that every connector's failure path
returns real cached `fallback` data or nothing -- never invented, randomized, or silently
relabeled-as-current data.

```bash
npx vitest run src/truesignal/provenance/no-fabrication.test.ts
```

Measured 2026-07-15: **22/22 tests passing**, 5 connectors covered.

## Cold start

How long a single fresh `node` process takes to load the built CLI and print `--help`.

```bash
npm run build
npx tsx benchmarks/cold-start.ts
```

Measured 2026-07-15 (10 runs, this machine): median **83.2ms** (min 64.6ms, max 107.6ms).

## Feed latency

Real wall-clock time for `truesignal feed --source cisa-kev` end to end: process start, a live
network call to the CISA-KEV catalog, parsing, provenance stamping, and printing. No API key
required for this source.

```bash
npm run build
npx tsx benchmarks/feed-latency.ts
```

Measured 2026-07-15 (3 runs, this machine, live network): 460.7ms, 789.7ms, 608.5ms --
**average 619.6ms**, 25 live items returned.

## Setup time

Fresh build, then `truesignal init`, then `truesignal feed`, with zero environment variables
set -- the actual first-run experience for a brand-new user, since CISA-KEV and GDELT need no
API key.

```bash
npx tsx benchmarks/setup-time.ts
```

Measured 2026-07-15 (this machine): build 3.17s, `init` 0.16s, `feed` (all 5 connectors, 2
usable with zero config) 10.94s -- **total 14.27s**. `feed` time here is dominated by live
network calls to CISA-KEV and GDELT and will vary run to run and by network conditions.

## What is not benchmarked here, and why

No performance number is published for Crucix, SpiderFoot, or IntelOwl in the README's
comparison table. Crucix's exemplar issues are cited by GitHub issue number and verified live
against the real repo (see the README's comparison table and its date stamp); SpiderFoot and
IntelOwl are compared on real, cited facts (license, install model, scope) rather than a
performance number, because none of the three were installed and run end to end in this pass.
Fabricating a number for a tool nobody ran here would violate the same no-fabrication principle
this project is built around.
