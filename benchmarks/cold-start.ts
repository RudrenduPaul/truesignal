/**
 * Cold start: how long a single fresh `node` process takes to load the built CLI and print
 * --help output. Requires `npm run build` first (this script does not build for you).
 *
 * Reproduce: npm run build && npx tsx benchmarks/cold-start.ts
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

const RUNS = 10;
const timesMs: number[] = [];

for (let i = 0; i < RUNS; i++) {
  const start = process.hrtime.bigint();
  execFileSync('node', [cliPath, '--help'], { stdio: 'ignore' });
  const end = process.hrtime.bigint();
  timesMs.push(Number(end - start) / 1_000_000);
}

const sorted = [...timesMs].sort((a, b) => a - b);
const median = sorted[Math.floor(sorted.length / 2)] as number;
const min = sorted[0] as number;
const max = sorted[sorted.length - 1] as number;

console.log(`Cold start (node dist/cli.js --help), ${RUNS} runs:`);
console.log(`  individual runs (ms): ${timesMs.map((t) => t.toFixed(1)).join(', ')}`);
console.log(`  median: ${median.toFixed(1)}ms`);
console.log(`  min: ${min.toFixed(1)}ms, max: ${max.toFixed(1)}ms`);
