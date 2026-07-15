import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { getCacheDir, readCache, writeCache } from './cache.js';
import type { FeedItem } from '../types.js';

const sampleItem: FeedItem = {
  id: 'cisa-kev:CVE-2026-00001',
  source: 'cisa-kev',
  title: 'Example vulnerability',
  url: 'https://nvd.nist.gov/vuln/detail/CVE-2026-00001',
  timestamp: '2026-07-01T00:00:00.000Z',
  status: 'live',
};

let tempDir: string;
let originalCacheDir: string | undefined;

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-cache-test-'));
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

describe('getCacheDir', () => {
  it('honors TRUESIGNAL_CACHE_DIR', () => {
    expect(getCacheDir()).toBe(tempDir);
  });

  it('falls back to ~/.truesignal/cache when unset', () => {
    delete process.env['TRUESIGNAL_CACHE_DIR'];
    expect(getCacheDir()).toContain('.truesignal');
    expect(getCacheDir()).toContain('cache');
  });
});

describe('writeCache / readCache', () => {
  it('returns null when nothing has ever been cached', async () => {
    expect(await readCache('cisa-kev')).toBeNull();
  });

  it('round-trips real items with a real fetchedAt timestamp', async () => {
    const before = Date.now();
    await writeCache('cisa-kev', [sampleItem]);
    const after = Date.now();

    const entry = await readCache('cisa-kev');
    expect(entry).not.toBeNull();
    expect(entry?.items).toEqual([sampleItem]);
    const fetchedAtMs = new Date(entry!.fetchedAt).getTime();
    expect(fetchedAtMs).toBeGreaterThanOrEqual(before);
    expect(fetchedAtMs).toBeLessThanOrEqual(after);
  });

  it('keeps caches for different sources independent', async () => {
    await writeCache('cisa-kev', [sampleItem]);
    await writeCache('gdelt', []);

    const kev = await readCache('cisa-kev');
    const gdelt = await readCache('gdelt');
    expect(kev?.items).toHaveLength(1);
    expect(gdelt?.items).toHaveLength(0);
  });

  it('overwrites the previous snapshot on the next successful write', async () => {
    await writeCache('cisa-kev', [sampleItem]);
    const second: FeedItem = { ...sampleItem, id: 'cisa-kev:CVE-2026-00002' };
    await writeCache('cisa-kev', [second]);

    const entry = await readCache('cisa-kev');
    expect(entry?.items).toEqual([second]);
  });

  it('treats a corrupt cache file as no cache, never as fabricated content', async () => {
    const { writeFile, mkdir } = await import('node:fs/promises');
    await mkdir(tempDir, { recursive: true });
    await writeFile(join(tempDir, 'cisa-kev.json'), '{ not valid json', 'utf-8');

    expect(await readCache('cisa-kev')).toBeNull();
  });

  it('treats a well-formed but wrong-shaped cache file as no cache', async () => {
    const { writeFile, mkdir } = await import('node:fs/promises');
    await mkdir(tempDir, { recursive: true });
    await writeFile(join(tempDir, 'cisa-kev.json'), JSON.stringify({ unexpected: true }), 'utf-8');

    expect(await readCache('cisa-kev')).toBeNull();
  });
});
