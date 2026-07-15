/**
 * The provenance-stamping layer -- the single most important module in this codebase.
 *
 * Every connector calls {@link fetchWithFallback} instead of hitting the network directly. It
 * enforces the product's core guarantee in code, not just in documentation:
 *
 *   1. A successful upstream fetch is stamped "live" and cached for future fallback use.
 *   2. A failed upstream fetch falls back to the last real cached snapshot, stamped "fallback"
 *      with an accurate age -- never silently presented as current.
 *   3. If there is no cache to fall back to, the connector returns nothing. It never invents,
 *      randomizes, or relabels stale data as live.
 */
import { readCache, writeCache } from './cache.js';
import type { FeedItem } from '../types.js';

/** The shape a connector's raw fetch produces, before this layer adds provenance status. */
export type UnstampedItem = Omit<FeedItem, 'status' | 'fallbackAgeSeconds'>;

/** Stamps raw upstream items as live and returns them, provenance-complete. */
export function stampLive(items: readonly UnstampedItem[]): FeedItem[] {
  return items.map((item) => ({ ...item, status: 'live' as const }));
}

/**
 * Stamps cached items as fallback, computing a real age in seconds from when they were cached
 * (`fetchedAt`) to now. Age is clamped to a minimum of 0 to guard against clock skew.
 */
export function stampFallback(
  items: readonly FeedItem[],
  fetchedAt: string,
  now = new Date(),
): FeedItem[] {
  const fetchedAtMs = new Date(fetchedAt).getTime();
  const ageSeconds = Math.max(0, Math.round((now.getTime() - fetchedAtMs) / 1000));
  return items.map((item) => ({
    ...item,
    status: 'fallback' as const,
    fallbackAgeSeconds: ageSeconds,
  }));
}

/**
 * Runs `fetchLive` against the real upstream source. On success, stamps and caches the result.
 * On failure, falls back to the last real cache entry for `source`, or returns an empty array if
 * none exists. This function is what every connector's failure path is tested against -- see
 * `no-fabrication.test.ts`.
 *
 * A local cache-write failure (disk full, read-only filesystem, permissions) is deliberately kept
 * out of the fallback path below: it has nothing to do with whether the upstream fetch succeeded,
 * and treating it the same as a network failure would mislabel data that was genuinely just
 * fetched live as a stale `fallback` -- the opposite of an honest provenance stamp.
 */
export async function fetchWithFallback(
  source: string,
  fetchLive: () => Promise<UnstampedItem[]>,
): Promise<FeedItem[]> {
  let raw: UnstampedItem[];
  try {
    raw = await fetchLive();
  } catch {
    const cached = await readCache(source);
    if (!cached || cached.items.length === 0) {
      return [];
    }
    return stampFallback(cached.items, cached.fetchedAt);
  }

  const live = stampLive(raw);
  try {
    await writeCache(source, live);
  } catch {
    // The fetch genuinely succeeded; a failure to persist it for future fallback use must not
    // turn this real live data into a mislabeled fallback or drop it.
  }
  return live;
}
