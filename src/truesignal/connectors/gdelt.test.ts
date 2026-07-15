import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { gdeltConnector } from './gdelt.js';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

let tempDir: string;

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-gdelt-test-'));
  process.env['TRUESIGNAL_CACHE_DIR'] = tempDir;
});

afterEach(async () => {
  vi.unstubAllGlobals();
  await rm(tempDir, { recursive: true, force: true });
});

describe('gdeltConnector', () => {
  it('requires no configuration', () => {
    expect(gdeltConnector.requiresConfig).toBe(false);
    expect(gdeltConnector.isConfigured()).toBe(true);
  });

  it('maps GDELT articles to real feed items with parsed timestamps', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          articles: [
            {
              url: 'https://example.com/news/a',
              title: 'Sample breach coverage',
              seendate: '20260315T134500Z',
              domain: 'example.com',
              sourcecountry: 'United States',
            },
          ],
        }),
      ),
    );

    const [item] = await gdeltConnector.fetchItems();
    expect(item).toMatchObject({
      id: 'gdelt:https://example.com/news/a',
      source: 'gdelt',
      url: 'https://example.com/news/a',
      timestamp: '2026-03-15T13:45:00.000Z',
      status: 'live',
    });
    expect(item?.summary).toContain('United States');
  });

  it('returns an empty array when the response has no articles field', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({})));
    const items = await gdeltConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('falls back rather than crashing on an unparseable seendate', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          articles: [
            {
              url: 'https://example.com/x',
              title: 't',
              seendate: 'not-a-date',
              domain: 'example.com',
            },
          ],
        }),
      ),
    );
    const items = await gdeltConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('returns an empty array on an HTTP error with no cache to fall back to', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 500)));
    const items = await gdeltConnector.fetchItems();
    expect(items).toEqual([]);
  });
});
