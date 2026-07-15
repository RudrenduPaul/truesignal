import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchWithFallback, stampFallback, stampLive } from './stamp.js';
import { readCache } from './cache.js';
import type { FeedItem } from '../types.js';
import type { UnstampedItem } from './stamp.js';

const unstamped: UnstampedItem = {
  id: 'gdelt:https://example.com/a',
  source: 'gdelt',
  title: 'Example article',
  url: 'https://example.com/a',
  timestamp: '2026-07-01T00:00:00.000Z',
};

let tempDir: string;
let originalCacheDir: string | undefined;

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-stamp-test-'));
  originalCacheDir = process.env['TRUESIGNAL_CACHE_DIR'];
  process.env['TRUESIGNAL_CACHE_DIR'] = tempDir;
});

afterEach(async () => {
  if (originalCacheDir === undefined) {
    delete process.env['TRUESIGNAL_CACHE_DIR'];
  } else {
    process.env['TRUESIGNAL_CACHE_DIR'] = originalCacheDir;
  }
  await rm(tempDir, { recursive: true, force: true });
});

describe('stampLive', () => {
  it('marks every item status: live and preserves the real upstream fields', () => {
    const [result] = stampLive([unstamped]);
    expect(result).toEqual({ ...unstamped, status: 'live' });
  });

  it('never adds a fallbackAgeSeconds field to a live item', () => {
    const [result] = stampLive([unstamped]);
    expect(result?.fallbackAgeSeconds).toBeUndefined();
  });
});

describe('stampFallback', () => {
  it('computes a real, non-negative age in seconds from fetchedAt to now', () => {
    const fetchedAt = '2026-07-01T00:00:00.000Z';
    const now = new Date('2026-07-01T00:10:00.000Z');
    const live: FeedItem = { ...unstamped, status: 'live' };

    const [result] = stampFallback([live], fetchedAt, now);
    expect(result?.status).toBe('fallback');
    expect(result?.fallbackAgeSeconds).toBe(600);
  });

  it('preserves the original event timestamp -- never rewrites it to "now"', () => {
    const fetchedAt = '2026-07-01T00:00:00.000Z';
    const now = new Date('2026-07-05T00:00:00.000Z');
    const live: FeedItem = { ...unstamped, status: 'live', timestamp: '2026-06-15T12:00:00.000Z' };

    const [result] = stampFallback([live], fetchedAt, now);
    expect(result?.timestamp).toBe('2026-06-15T12:00:00.000Z');
  });

  it('clamps age to zero rather than going negative under clock skew', () => {
    const fetchedAt = '2026-07-01T00:10:00.000Z';
    const now = new Date('2026-07-01T00:00:00.000Z'); // "now" before fetchedAt
    const live: FeedItem = { ...unstamped, status: 'live' };

    const [result] = stampFallback([live], fetchedAt, now);
    expect(result?.fallbackAgeSeconds).toBe(0);
  });
});

describe('fetchWithFallback', () => {
  it('returns live items and caches them on a successful fetch', async () => {
    const fetchLive = vi.fn().mockResolvedValue([unstamped]);

    const items = await fetchWithFallback('gdelt', fetchLive);

    expect(items).toEqual([{ ...unstamped, status: 'live' }]);
    const cached = await readCache('gdelt');
    expect(cached?.items).toEqual([{ ...unstamped, status: 'live' }]);
  });

  it('falls back to the real cache, stamped fallback, when the live fetch throws', async () => {
    const okFetch = vi.fn().mockResolvedValue([unstamped]);
    await fetchWithFallback('gdelt', okFetch); // seed a real cache entry

    const failingFetch = vi.fn().mockRejectedValue(new Error('upstream unreachable'));
    const items = await fetchWithFallback('gdelt', failingFetch);

    expect(items).toHaveLength(1);
    expect(items[0]?.status).toBe('fallback');
    expect(items[0]?.url).toBe(unstamped.url);
    expect(typeof items[0]?.fallbackAgeSeconds).toBe('number');
    expect(items[0]?.fallbackAgeSeconds).toBeGreaterThanOrEqual(0);
  });

  it('returns an empty array -- never fabricated data -- when the fetch fails and no cache exists', async () => {
    const failingFetch = vi.fn().mockRejectedValue(new Error('upstream unreachable'));

    const items = await fetchWithFallback('gdelt', failingFetch);

    expect(items).toEqual([]);
  });

  it('still returns real live data, stamped live, when the upstream fetch succeeds but the local cache write fails', async () => {
    // Force writeCache's mkdir(dir, { recursive: true }) to fail with ENOTDIR regardless of the
    // OS user's privileges (a chmod-based permission test is unreliable when tests run as root,
    // e.g. in a container, since root bypasses filesystem permission checks): make a path segment
    // of the cache directory a regular file instead of a directory.
    const blockerPath = join(tempDir, 'blocked-by-a-file');
    await writeFile(blockerPath, 'not a directory', 'utf-8');
    process.env['TRUESIGNAL_CACHE_DIR'] = join(blockerPath, 'cache');

    const fetchLive = vi.fn().mockResolvedValue([unstamped]);
    const items = await fetchWithFallback('gdelt', fetchLive);

    // The upstream fetch genuinely succeeded -- a local disk error persisting it to cache must
    // never downgrade real live data into a mislabeled fallback, or silently drop it.
    expect(items).toEqual([{ ...unstamped, status: 'live' }]);
  });
});
