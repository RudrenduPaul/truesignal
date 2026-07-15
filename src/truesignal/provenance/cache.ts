/**
 * File-based cache for the last successful live fetch per connector.
 *
 * This is what makes a real `fallback` item possible: when a source is unreachable, a connector
 * serves the last genuinely-fetched-live data it has on disk, stamped with its real age -- never
 * invented data. If nothing has ever been fetched successfully, there is nothing to fall back to,
 * and the connector must return an empty array instead.
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import type { FeedItem } from '../types.js';

export interface CacheEntry {
  /** Real ISO-8601 timestamp of when this cache entry was written, i.e. the last live fetch. */
  fetchedAt: string;
  /** The real live items captured at that fetch. */
  items: FeedItem[];
}

/**
 * Resolves the cache directory. Overridable via TRUESIGNAL_CACHE_DIR (used by tests, and by
 * anyone who wants cache state outside their home directory) -- defaults to ~/.truesignal/cache.
 */
export function getCacheDir(): string {
  return process.env['TRUESIGNAL_CACHE_DIR'] ?? join(homedir(), '.truesignal', 'cache');
}

function cacheFilePath(source: string): string {
  return join(getCacheDir(), `${source}.json`);
}

/** Persists the given items as the latest known-live snapshot for `source`. */
export async function writeCache(source: string, items: FeedItem[]): Promise<void> {
  const dir = getCacheDir();
  await mkdir(dir, { recursive: true });
  const entry: CacheEntry = { fetchedAt: new Date().toISOString(), items };
  await writeFile(cacheFilePath(source), JSON.stringify(entry, null, 2), 'utf-8');
}

/**
 * Reads the last cached snapshot for `source`. Returns null if no cache exists yet, or if the
 * cache file is missing/corrupt -- a connector must treat "cannot prove what was cached" the same
 * as "nothing cached" rather than guessing at its contents.
 */
export async function readCache(source: string): Promise<CacheEntry | null> {
  try {
    const raw = await readFile(cacheFilePath(source), 'utf-8');
    const parsed = JSON.parse(raw) as CacheEntry;
    if (!parsed || typeof parsed.fetchedAt !== 'string' || !Array.isArray(parsed.items)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}
