/**
 * Testable logic behind the CLI. `cli.ts` wires this up to commander and process.exit(); every
 * function here is pure enough to unit test without spawning a real process.
 */
import type { Connector, FeedItem, ItemStatus } from './types.js';

/** Exit codes this CLI uses. Documented here and in the per-subcommand --help text. */
export const ExitCode = {
  /** Command completed successfully. */
  Success: 0,
  /** Unexpected/uncategorized error. */
  GeneralError: 1,
  /** The requested connector(s) exist but none are configured -- nothing could run. */
  NoConnectorsConfigured: 2,
  /** A configured connector's upstream fetch failed and produced no fallback data either. */
  NetworkError: 3,
  /** `verify <item-id>` was given an id that doesn't parse or names an unknown source. */
  InvalidItemId: 4,
} as const;

export type ExitCodeValue = (typeof ExitCode)[keyof typeof ExitCode];

export interface ConnectorStatus {
  name: string;
  label: string;
  requiresConfig: boolean;
  configured: boolean;
  missingEnvVars: string[];
}

/** Computes the configuration status of every connector, for `truesignal init`. */
export function getConnectorStatuses(connectors: readonly Connector[]): ConnectorStatus[] {
  return connectors.map((connector) => ({
    name: connector.name,
    label: connector.label,
    requiresConfig: connector.requiresConfig,
    configured: connector.isConfigured(),
    missingEnvVars:
      connector.requiresConfig && !connector.isConfigured() ? [...connector.configEnvVars] : [],
  }));
}

/** Human-readable report for `truesignal init`. */
export function formatInitReport(statuses: readonly ConnectorStatus[]): string {
  const lines: string[] = ['truesignal connector status:', ''];
  for (const status of statuses) {
    if (!status.requiresConfig) {
      lines.push(`  [ready]        ${status.label} (${status.name}) -- no configuration needed`);
    } else if (status.configured) {
      lines.push(`  [ready]        ${status.label} (${status.name}) -- configured`);
    } else {
      lines.push(
        `  [not configured] ${status.label} (${status.name}) -- set ${status.missingEnvVars.join(', ')}`,
      );
    }
  }
  const readyCount = statuses.filter((s) => !s.requiresConfig || s.configured).length;
  lines.push('', `${readyCount}/${statuses.length} connectors ready.`);
  if (readyCount === 0) {
    lines.push(
      'No connectors are usable. This should not happen -- CISA-KEV and GDELT need no configuration.',
    );
  } else {
    if (readyCount < statuses.length) {
      lines.push(
        'Set the missing environment variables above to enable the rest. See .env.example.',
      );
    }
    lines.push('Next: run "truesignal feed" to see your feed now.');
  }
  return lines.join('\n');
}

export interface ConnectorSelection {
  /** Connectors to actually query. */
  toQuery: Connector[];
  /** Connectors that exist but are not configured, skipped rather than failed on. */
  skipped: Connector[];
  /** Set if `--source` named a connector that does not exist. */
  unknownSource?: string;
}

/**
 * Resolves which connectors `truesignal feed` should query, given an optional `--source` filter.
 * Unconfigured connectors are skipped (reported, never crashed on); an unknown `--source` name is
 * reported back as an error rather than silently ignored.
 */
export function selectConnectors(
  allConnectors: readonly Connector[],
  sourceFilter?: string,
): ConnectorSelection {
  let candidates = allConnectors;
  if (sourceFilter) {
    const match = allConnectors.find((c) => c.name === sourceFilter);
    if (!match) {
      return { toQuery: [], skipped: [], unknownSource: sourceFilter };
    }
    candidates = [match];
  }
  const toQuery = candidates.filter((c) => !c.requiresConfig || c.isConfigured());
  const skipped = candidates.filter((c) => c.requiresConfig && !c.isConfigured());
  return { toQuery, skipped };
}

function relativeAge(timestamp: string, now: Date): string {
  const ms = now.getTime() - new Date(timestamp).getTime();
  const seconds = Math.max(0, Math.round(ms / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

// Matches C0 controls (except handled separately), DEL, and C1 controls -- built from explicit
// \xNN escapes rather than a literal character class so no raw control byte ever sits in this
// source file.
// eslint-disable-next-line no-control-regex -- intentional: stripping control chars is the point
const CONTROL_CHAR_PATTERN = new RegExp('[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F\\x7F-\\x9F]', 'g');

/**
 * Strips control characters (C0/C1, DEL) from untrusted upstream text before it reaches a
 * terminal. Reddit and Telegram content is attacker-controlled -- a crafted post title or
 * message could otherwise carry ANSI/OSC escape sequences (cursor manipulation, terminal-title
 * spoofing, an OSC-8 hyperlink escape that visually disguises the printed URL) straight into
 * the user's terminal via `console.log`.
 */
function sanitizeForTerminal(text: string): string {
  return text.replace(CONTROL_CHAR_PATTERN, '');
}

/** Formats one feed item as a single human-readable line. */
export function formatFeedItemHuman(item: FeedItem, now = new Date()): string {
  const tag =
    item.status === 'live'
      ? '[live]'
      : `[fallback, ${formatDuration(item.fallbackAgeSeconds ?? 0)} old]`;
  const title = sanitizeForTerminal(item.title);
  const url = sanitizeForTerminal(item.url);
  return `${tag} ${item.source}: ${title} -- ${url} -- ${relativeAge(item.timestamp, now)}`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days}d`;
}

/** Splits a feed item id (`${source}:${nativeId}`) into its source and native-id parts. */
export function parseItemId(itemId: string): { source: string; nativeId: string } | null {
  const separatorIndex = itemId.indexOf(':');
  if (separatorIndex <= 0 || separatorIndex === itemId.length - 1) {
    return null;
  }
  return {
    source: itemId.slice(0, separatorIndex),
    nativeId: itemId.slice(separatorIndex + 1),
  };
}

export interface FeedRunResult {
  items: FeedItem[];
  skipped: string[];
  failures: { source: string; error: string }[];
  unknownSource?: string;
}

/**
 * Runs `truesignal feed` end to end against real connectors: resolves which to query, fetches
 * them concurrently, and never lets one connector's failure take down the others.
 */
export async function runFeed(
  connectors: readonly Connector[],
  sourceFilter?: string,
): Promise<FeedRunResult> {
  const selection = selectConnectors(connectors, sourceFilter);
  if (selection.unknownSource) {
    return { items: [], skipped: [], failures: [], unknownSource: selection.unknownSource };
  }

  const settled = await Promise.allSettled(selection.toQuery.map((c) => c.fetchItems()));
  const items: FeedItem[] = [];
  const failures: { source: string; error: string }[] = [];
  settled.forEach((outcome, index) => {
    const connector = selection.toQuery[index];
    if (!connector) return;
    if (outcome.status === 'fulfilled') {
      items.push(...outcome.value);
    } else {
      failures.push({
        source: connector.name,
        error: outcome.reason instanceof Error ? outcome.reason.message : String(outcome.reason),
      });
    }
  });

  return {
    items,
    skipped: selection.skipped.map((c) => c.name),
    failures,
  };
}

export type VerifyErrorKind = 'invalid-id' | 'unknown-source' | 'not-configured' | 'network-error';

export interface VerifyResult {
  itemId: string;
  found: boolean;
  status?: ItemStatus;
  url?: string;
  timestamp?: string;
  fallbackAgeSeconds?: number;
  errorKind?: VerifyErrorKind;
  errorMessage?: string;
}

/** Re-fetches the named connector and confirms whether `itemId` still resolves to real data. */
export async function runVerify(
  connectors: readonly Connector[],
  itemId: string,
): Promise<VerifyResult> {
  const parsed = parseItemId(itemId);
  if (!parsed) {
    return {
      itemId,
      found: false,
      errorKind: 'invalid-id',
      errorMessage: `Could not parse item id "${itemId}". Expected format: <source>:<native-id>, e.g. cisa-kev:CVE-2026-12345`,
    };
  }

  const connector = connectors.find((c) => c.name === parsed.source);
  if (!connector) {
    return {
      itemId,
      found: false,
      errorKind: 'unknown-source',
      errorMessage: `Unknown source "${parsed.source}" in item id "${itemId}". Known sources: ${connectors.map((c) => c.name).join(', ')}`,
    };
  }

  if (connector.requiresConfig && !connector.isConfigured()) {
    return {
      itemId,
      found: false,
      errorKind: 'not-configured',
      errorMessage: `Connector "${connector.name}" is not configured. Run "truesignal init" to see what's needed.`,
    };
  }

  let items: FeedItem[];
  try {
    items = await connector.fetchItems();
  } catch (error) {
    return {
      itemId,
      found: false,
      errorKind: 'network-error',
      errorMessage: `Failed to verify: ${error instanceof Error ? error.message : String(error)}`,
    };
  }

  const found = items.find((item) => item.id === itemId);
  if (!found) {
    return { itemId, found: false };
  }
  return {
    itemId,
    found: true,
    status: found.status,
    url: found.url,
    timestamp: found.timestamp,
    ...(found.fallbackAgeSeconds !== undefined
      ? { fallbackAgeSeconds: found.fallbackAgeSeconds }
      : {}),
  };
}
