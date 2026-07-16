/**
 * Feed latency: real wall-clock time for `truesignal feed --source cisa-kev` end to end --
 * process start, a real network call to the live CISA-KEV catalog, parsing, provenance
 * stamping, and printing. No key required for this source. Requires `npm run build` first.
 *
 * Reproduce: npm run build && npx tsx benchmarks/feed-latency.ts
 */
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const cliPath = join(repoRoot, 'dist', 'cli.js');

if (!existsSync(cliPath)) {
  console.error('dist/cli.js not found -- run `npm run build` first.');
  process.exit(1);
}

const RUNS = 3;
const timesMs: number[] = [];
let lastOutput = '';

for (let i = 0; i < RUNS; i++) {
  const start = process.hrtime.bigint();
  lastOutput = execFileSync('node', [cliPath, 'feed', '--source', 'cisa-kev'], {
    encoding: 'utf-8',
  });
  const end = process.hrtime.bigint();
  timesMs.push(Number(end - start) / 1_000_000);
}

const itemCount = lastOutput.trim().split('\n').filter(Boolean).length;
const avg = timesMs.reduce((a, b) => a + b, 0) / timesMs.length;

console.log(`Feed latency (truesignal feed --source cisa-kev), ${RUNS} real network runs:`);
console.log(`  individual runs (ms): ${timesMs.map((t) => t.toFixed(1)).join(', ')}`);
console.log(`  average: ${avg.toFixed(1)}ms`);
console.log(`  items returned on last run: ${itemCount}`);
console.log('  (this hits the live CISA-KEV catalog over the network -- numbers vary run to run)');
