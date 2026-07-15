import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { redditConnector } from './reddit.js';
import { ConnectorNotConfiguredError } from '../types.js';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

let tempDir: string;
const originalId = process.env['REDDIT_CLIENT_ID'];
const originalSecret = process.env['REDDIT_CLIENT_SECRET'];
const originalSubreddit = process.env['REDDIT_SUBREDDIT'];

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-reddit-test-'));
  process.env['TRUESIGNAL_CACHE_DIR'] = tempDir;
});

afterEach(async () => {
  vi.unstubAllGlobals();
  for (const [key, value] of [
    ['REDDIT_CLIENT_ID', originalId],
    ['REDDIT_CLIENT_SECRET', originalSecret],
    ['REDDIT_SUBREDDIT', originalSubreddit],
  ] as const) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  await rm(tempDir, { recursive: true, force: true });
});

describe('redditConnector', () => {
  it('is unconfigured unless both client id and secret are present', async () => {
    delete process.env['REDDIT_CLIENT_ID'];
    delete process.env['REDDIT_CLIENT_SECRET'];
    expect(redditConnector.isConfigured()).toBe(false);

    process.env['REDDIT_CLIENT_ID'] = 'id-only';
    expect(redditConnector.isConfigured()).toBe(false);

    process.env['REDDIT_CLIENT_SECRET'] = 'secret-too';
    expect(redditConnector.isConfigured()).toBe(true);
  });

  it('throws ConnectorNotConfiguredError instead of fetching when unconfigured', async () => {
    delete process.env['REDDIT_CLIENT_ID'];
    delete process.env['REDDIT_CLIENT_SECRET'];
    await expect(redditConnector.fetchItems()).rejects.toBeInstanceOf(ConnectorNotConfiguredError);
  });

  it('performs OAuth via the official token endpoint, never the unauthenticated .json scrape', async () => {
    process.env['REDDIT_CLIENT_ID'] = 'fake-id';
    process.env['REDDIT_CLIENT_SECRET'] = 'fake-secret';
    const fetchMock = vi.fn().mockImplementation(async (input: string | URL) => {
      const url = input.toString();
      if (url.includes('access_token')) {
        return jsonResponse({ access_token: 'fake-token', token_type: 'bearer', expires_in: 3600 });
      }
      return jsonResponse({
        data: {
          children: [
            {
              data: {
                id: 'p1',
                title: 'Sample',
                permalink: '/r/netsec/comments/p1/sample/',
                created_utc: 1750000000,
                subreddit: 'netsec',
              },
            },
          ],
        },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const items = await redditConnector.fetchItems();

    expect(items).toHaveLength(1);
    expect(items[0]?.url).toBe('https://reddit.com/r/netsec/comments/p1/sample/');
    for (const call of fetchMock.mock.calls) {
      const url = (call[0] as string | URL).toString();
      expect(url).not.toContain('.json');
      expect(url).not.toContain('www.reddit.com/r/');
    }
  });

  it('falls back rather than fabricating when the token request itself fails', async () => {
    process.env['REDDIT_CLIENT_ID'] = 'fake-id';
    process.env['REDDIT_CLIENT_SECRET'] = 'fake-secret';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 401)));
    const items = await redditConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('respects REDDIT_SUBREDDIT when set', async () => {
    process.env['REDDIT_CLIENT_ID'] = 'fake-id';
    process.env['REDDIT_CLIENT_SECRET'] = 'fake-secret';
    process.env['REDDIT_SUBREDDIT'] = 'osint';
    const fetchMock = vi.fn().mockImplementation(async (input: string | URL) => {
      const url = input.toString();
      if (url.includes('access_token')) {
        return jsonResponse({ access_token: 'fake-token', token_type: 'bearer', expires_in: 3600 });
      }
      expect(url).toContain('/r/osint/new');
      return jsonResponse({ data: { children: [] } });
    });
    vi.stubGlobal('fetch', fetchMock);

    await redditConnector.fetchItems();
    expect(fetchMock).toHaveBeenCalled();
  });
});
