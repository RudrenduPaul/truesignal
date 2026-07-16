/**
 * Setup / time-to-first-honest-word: how long a brand-new user waits from a clean build to
 * seeing their first real feed item, with zero environment variables set (the actual
 * first-run experience -- CISA-KEV and GDELT need no API key). This script builds from
 * scratch, so it takes longer than a normal `npm run build` you'd run once.
 *
 * Reproduce: npx tsx benchmarks/setup-time.ts
 */
import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const cliPath = join(repoRoot, 'dist', 'cli.js');
const cleanEnv = { PATH: process.env['PATH'] ?? '', HOME: process.env['HOME'] ?? '' };

function timeMs(fn: () => void): number {
  const start = process.hrtime.bigint();
  fn();
  const end = process.hrtime.bigint();
  return Number(end - start) / 1_000_000;
}

rmSync(join(repoRoot, 'dist'), { recursive: true, force: true });

const buildMs = timeMs(() => {
  execFileSync('npm', ['run', 'build'], { cwd: repoRoot, stdio: 'ignore' });
});

const initMs = timeMs(() => {
  execFileSync('node', [cliPath, 'init'], { env: cleanEnv, stdio: 'ignore' });
});

const feedMs = timeMs(() => {
  execFileSync('node', [cliPath, 'feed'], { env: cleanEnv, stdio: 'ignore' });
});

const totalMs = buildMs + initMs + feedMs;

console.log('Setup time (fresh build -> init -> feed, zero env vars set):');
console.log(`  npm run build: ${(buildMs / 1000).toFixed(2)}s`);
console.log(`  truesignal init: ${(initMs / 1000).toFixed(2)}s`);
console.log(`  truesignal feed (all 5 connectors, 2 usable with zero config): ${(feedMs / 1000).toFixed(2)}s`);
console.log(`  total: ${(totalMs / 1000).toFixed(2)}s`);
console.log(
  '  (feed time is dominated by real live network calls to CISA-KEV and GDELT -- varies run to run)',
);
