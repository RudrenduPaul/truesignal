#!/usr/bin/env node
/**
 * truesignal CLI entry point. This file is deliberately thin -- it wires commander's argument
 * parsing to the testable logic in cli-helpers.ts and sets process exit codes. See ExitCode in
 * cli-helpers.ts for what each code means.
 */
import { Command } from 'commander';
import { allConnectors } from './connectors/index.js';
import {
  ExitCode,
  formatFeedItemHuman,
  formatInitReport,
  getConnectorStatuses,
  runFeed,
  runVerify,
} from './cli-helpers.js';

const program = new Command();

program
  .name('truesignal')
  .description(
    'A provenance-first OSINT/security intelligence feed. Every item carries a real source ' +
      'URL, a real timestamp, and an explicit live/fallback flag -- never a fabricated or ' +
      'silently-replayed data point.',
  )
  .version('0.1.0');

program
  .command('init')
  .description(
    'Check which connectors are ready to use right now and which environment variables are ' +
      'still needed for the rest. CISA-KEV and GDELT need no configuration -- truesignal works ' +
      'with zero setup for those two sources.',
  )
  .option('--json', 'print machine-readable JSON instead of a human-readable report')
  .action((opts: { json?: boolean }) => {
    const statuses = getConnectorStatuses(allConnectors);
    if (opts.json) {
      console.log(JSON.stringify({ connectors: statuses }, null, 2));
    } else {
      console.log(formatInitReport(statuses));
    }
    const readyCount = statuses.filter((s) => !s.requiresConfig || s.configured).length;
    process.exitCode = readyCount > 0 ? ExitCode.Success : ExitCode.NoConnectorsConfigured;
  });

program
  .command('feed')
  .description(
    'Pull the current feed from every configured connector, or one connector with --source. ' +
      'Prints human-readable output by default; use --json for a stable, agent-parseable schema.',
  )
  .option('--source <name>', 'only pull from this connector, e.g. cisa-kev, gdelt')
  .option('--json', 'print machine-readable JSON instead of human-readable text')
  .action(async (opts: { source?: string; json?: boolean }) => {
    const result = await runFeed(allConnectors, opts.source);

    if (result.unknownSource) {
      const known = allConnectors.map((c) => c.name).join(', ');
      process.stderr.write(`Unknown source "${result.unknownSource}". Known sources: ${known}\n`);
      process.exitCode = ExitCode.GeneralError;
      return;
    }

    if (result.items.length === 0 && result.skipped.length > 0 && result.failures.length === 0) {
      if (opts.json) {
        console.log(JSON.stringify(result, null, 2));
      } else {
        process.stderr.write(
          `No connectors are configured to run. Missing: ${result.skipped.join(', ')}. ` +
            `Run "truesignal init" to see what's needed.\n`,
        );
      }
      process.exitCode = ExitCode.NoConnectorsConfigured;
      return;
    }

    if (opts.json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      if (result.skipped.length > 0) {
        console.log(`Skipped (not configured): ${result.skipped.join(', ')}`);
      }
      if (result.items.length === 0) {
        console.log('No items returned.');
      }
      for (const item of result.items) {
        console.log(formatFeedItemHuman(item));
      }
      for (const failure of result.failures) {
        process.stderr.write(`${failure.source}: ${failure.error}\n`);
      }
    }

    if (result.items.length === 0 && result.failures.length > 0) {
      process.exitCode = ExitCode.NetworkError;
    } else {
      process.exitCode = ExitCode.Success;
    }
  });

program
  .command('verify')
  .argument('<item-id>', 'a feed item id from `truesignal feed`, e.g. cisa-kev:CVE-2026-12345')
  .description(
    'Re-fetch the source connector named in <item-id> and confirm whether that item still ' +
      'resolves to real, live provenance, has fallen back to cached data, or can no longer be found.',
  )
  .option('--json', 'print machine-readable JSON instead of human-readable text')
  .action(async (itemId: string, opts: { json?: boolean }) => {
    const result = await runVerify(allConnectors, itemId);

    if (opts.json) {
      console.log(JSON.stringify(result, null, 2));
    } else if (result.errorMessage) {
      process.stderr.write(`${result.errorMessage}\n`);
    } else if (result.found) {
      const provenance =
        result.status === 'live'
          ? 'LIVE'
          : `FALLBACK (${result.fallbackAgeSeconds ?? 0}s old cached data)`;
      console.log(`${itemId}: ${provenance} -- ${result.url} -- ${result.timestamp}`);
    } else {
      console.log(
        `${itemId}: not found in the current feed (it may have rolled off, or never existed).`,
      );
    }

    if (result.errorKind === 'invalid-id' || result.errorKind === 'unknown-source') {
      process.exitCode = ExitCode.InvalidItemId;
    } else if (result.errorKind === 'not-configured') {
      process.exitCode = ExitCode.NoConnectorsConfigured;
    } else if (result.errorKind === 'network-error') {
      process.exitCode = ExitCode.NetworkError;
    } else if (!result.found) {
      process.exitCode = ExitCode.GeneralError;
    } else {
      process.exitCode = ExitCode.Success;
    }
  });

program.parseAsync(process.argv).catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = ExitCode.GeneralError;
});
