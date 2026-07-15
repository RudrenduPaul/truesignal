/**
 * Shared types for truesignal's connector and provenance layers.
 *
 * The single hardest rule in this codebase: every FeedItem this program ever emits must be
 * traceable to a real upstream response. `status` records whether the item came from a live
 * fetch or a cached fallback -- there is no third path where data is invented.
 */

/** Whether a feed item came from a live upstream fetch or a cached fallback. */
export type ItemStatus = 'live' | 'fallback';

/** A single item surfaced by a connector, stamped with real provenance. */
export interface FeedItem {
  /** Stable id, unique within a source: `${source}:${sourceNativeId}`. */
  id: string;
  /** The connector name that produced this item, e.g. "cisa-kev". */
  source: string;
  /** Human-readable title. */
  title: string;
  /** Real, dereferenceable URL to the upstream item. Never a fabricated or placeholder link. */
  url: string;
  /**
   * Real ISO-8601 timestamp from the upstream source describing when the underlying event or
   * publication occurred. Never rewritten to "now" -- for a `fallback` item this is the original
   * event time, not the time the fallback was served.
   */
  timestamp: string;
  /** "live" if fetched from the upstream source just now, "fallback" if served from cache. */
  status: ItemStatus;
  /**
   * Present only when `status` is "fallback": how many seconds old the cached data being shown
   * is, measured from when it was originally fetched live to now. Required whenever status is
   * "fallback" so a caller can never mistake stale data for current.
   */
  fallbackAgeSeconds?: number;
  /** Optional short human-readable summary. */
  summary?: string;
}

/** Raised when a connector's config is missing and code calls fetchItems() anyway. */
export class ConnectorNotConfiguredError extends Error {
  constructor(public readonly connectorName: string) {
    super(
      `Connector "${connectorName}" requires configuration that is not present. ` +
        `Run "truesignal init" to see what is missing.`,
    );
    this.name = 'ConnectorNotConfiguredError';
  }
}

/**
 * A source connector. Every connector in src/truesignal/connectors/ implements this interface so
 * connectors are swappable plugins behind one common contract -- adding a new source (NVD,
 * Shodan, VirusTotal, ...) is a new file implementing this interface, never a change to the CLI
 * or provenance layer.
 */
export interface Connector {
  /** Stable machine-readable name, e.g. "cisa-kev". Used as the `--source` flag value. */
  readonly name: string;
  /** Human-readable label, e.g. "CISA Known Exploited Vulnerabilities". */
  readonly label: string;
  /** True if this connector needs BYO credentials (an API key, token, or app registration). */
  readonly requiresConfig: boolean;
  /** The environment variable names this connector reads credentials from, if any. */
  readonly configEnvVars: readonly string[];
  /** Returns true if every required env var this connector needs is present and non-empty. */
  isConfigured(): boolean;
  /**
   * Fetches the current items from this source.
   *
   * Contract: on success, returns real `status: "live"` items with real timestamps and URLs. On
   * upstream failure, returns real cached items stamped `status: "fallback"` with an accurate
   * `fallbackAgeSeconds`, or an empty array if no cache exists. Never returns synthetic,
   * randomized, or silently-relabeled-as-current data. Throws {@link ConnectorNotConfiguredError}
   * if called while `requiresConfig` is true and `isConfigured()` is false.
   */
  fetchItems(): Promise<FeedItem[]>;
}
