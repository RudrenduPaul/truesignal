/**
 * The single most important test file in this repo.
 *
 * It proves, for every connector this product ships, that a failed upstream fetch never results
 * in fabricated, randomized, or silently-relabeled-as-current data -- only a real cached
 * `fallback` item with an honest age, or nothing at all. This is the entire product claim; if any
 * of these tests fail, truesignal is shipping the exact bug it exists to not repeat.
 */
import { mkdtemp, readdir, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cisaKevConnector } from '../connectors/cisa-kev.js';
import { cloudflareRadarConnector } from '../connectors/cloudflare-radar.js';
import { redditConnector } from '../connectors/reddit.js';
import { telegramConnector } from '../connectors/telegram.js';
import { gdeltConnector } from '../connectors/gdelt.js';
import { allConnectors } from '../connectors/index.js';
import { ConnectorNotConfiguredError, type Connector, type FeedItem } from '../types.js';

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status: ok ? status : 500,
    headers: { 'content-type': 'application/json' },
  });
}

interface FixtureCase {
  connector: Connector;
  /** Env vars to set so the connector reports itself configured. */
  env: Record<string, string>;
  /** Mocks a successful upstream response for every fetch() call this connector makes. */
  mockSuccess: () => void;
  /** Mocks a failing upstream response (HTTP-level or rejected) for every fetch() call. */
  mockFailure: () => void;
}

const originalEnv = { ...process.env };
let tempDir: string;

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-no-fab-test-'));
  process.env['TRUESIGNAL_CACHE_DIR'] = tempDir;
});

afterEach(async () => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  for (const key of Object.keys(process.env)) {
    if (!(key in originalEnv)) delete process.env[key];
  }
  Object.assign(process.env, originalEnv);
  await rm(tempDir, { recursive: true, force: true });
});

const cases: FixtureCase[] = [
  {
    connector: cisaKevConnector,
    env: {},
    mockSuccess: () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse({
            vulnerabilities: [
              {
                cveID: 'CVE-2026-00001',
                vendorProject: 'Acme',
                product: 'Widget',
                vulnerabilityName: 'Sample RCE',
                dateAdded: '2026-01-01',
                shortDescription: 'A sample description.',
              },
            ],
          }),
        ),
      );
    },
    mockFailure: () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network unreachable')));
    },
  },
  {
    connector: gdeltConnector,
    env: {},
    mockSuccess: () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse({
            articles: [
              {
                url: 'https://example.com/article-a',
                title: 'Sample security article',
                seendate: '20260101T000000Z',
                domain: 'example.com',
              },
            ],
          }),
        ),
      );
    },
    mockFailure: () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network unreachable')));
    },
  },
  {
    connector: cloudflareRadarConnector,
    env: { CLOUDFLARE_RADAR_API_TOKEN: 'fake-token-for-tests' },
    mockSuccess: () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse({
            success: true,
            result: {
              trafficAnomalies: [
                {
                  uuid: 'anomaly-1',
                  startDate: '2026-01-01T00:00:00Z',
                  type: 'outage',
                  asnDetails: { asn: 64500, name: 'Example Net' },
                },
              ],
            },
          }),
        ),
      );
    },
    mockFailure: () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network unreachable')));
    },
  },
  {
    connector: redditConnector,
    env: { REDDIT_CLIENT_ID: 'fake-id', REDDIT_CLIENT_SECRET: 'fake-secret' },
    mockSuccess: () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockImplementation(async (input: string | URL) => {
          const url = input.toString();
          if (url.includes('access_token')) {
            return jsonResponse({
              access_token: 'fake-access-token',
              token_type: 'bearer',
              expires_in: 3600,
            });
          }
          return jsonResponse({
            data: {
              children: [
                {
                  data: {
                    id: 'abc123',
                    title: 'Sample post',
                    permalink: '/r/netsec/comments/abc123/sample_post/',
                    created_utc: 1750000000,
                    subreddit: 'netsec',
                  },
                },
              ],
            },
          });
        }),
      );
    },
    mockFailure: () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network unreachable')));
    },
  },
  {
    connector: telegramConnector,
    env: { TELEGRAM_BOT_TOKEN: 'fake-bot-token' },
    mockSuccess: () => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(
          jsonResponse({
            ok: true,
            result: [
              {
                update_id: 1,
                channel_post: {
                  message_id: 5,
                  date: 1750000000,
                  chat: { id: 111, title: 'Example Channel', username: 'examplechan' },
                  text: 'Sample channel post',
                },
              },
            ],
          }),
        ),
      );
    },
    mockFailure: () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network unreachable')));
    },
  },
];

describe.each(cases)(
  '$connector.name no-fabrication guarantee',
  ({ connector, env, mockSuccess, mockFailure }) => {
    beforeEach(() => {
      for (const [key, value] of Object.entries(env)) {
        process.env[key] = value;
      }
    });

    it('returns real live items on a successful fetch, each stamped status: live', async () => {
      mockSuccess();
      const items = await connector.fetchItems();
      expect(items.length).toBeGreaterThan(0);
      for (const item of items) {
        expect(item.status).toBe('live');
        expect(item.fallbackAgeSeconds).toBeUndefined();
        expect(item.url).toMatch(/^https:\/\//);
        expect(Number.isNaN(new Date(item.timestamp).getTime())).toBe(false);
      }
    });

    it('returns an empty array (never fabricated data) when the source fails and no cache exists', async () => {
      mockFailure();
      const items = await connector.fetchItems();
      expect(items).toEqual([]);
    });

    it('falls back to real cached data, honestly flagged, when the source fails after a prior success', async () => {
      mockSuccess();
      const liveItems = await connector.fetchItems();
      expect(liveItems.length).toBeGreaterThan(0);

      mockFailure();
      const fallbackItems = await connector.fetchItems();

      expect(fallbackItems).toHaveLength(liveItems.length);
      for (let i = 0; i < fallbackItems.length; i++) {
        const fallbackItem = fallbackItems[i] as FeedItem;
        const liveItem = liveItems[i] as FeedItem;
        expect(fallbackItem.status).toBe('fallback');
        // The real event URL and timestamp must be identical to what was really fetched live --
        // never rewritten, never replaced with a synthetic value.
        expect(fallbackItem.url).toBe(liveItem.url);
        expect(fallbackItem.timestamp).toBe(liveItem.timestamp);
        expect(fallbackItem.id).toBe(liveItem.id);
        expect(typeof fallbackItem.fallbackAgeSeconds).toBe('number');
        expect(fallbackItem.fallbackAgeSeconds).toBeGreaterThanOrEqual(0);
      }
    });
  },
);

describe('connectors that require configuration', () => {
  const configuredCases = cases.filter((c) => c.connector.requiresConfig);

  it.each(configuredCases)(
    '$connector.name reports isConfigured() === false with no env vars set',
    ({ connector }) => {
      for (const envVar of connector.configEnvVars) {
        delete process.env[envVar];
      }
      expect(connector.isConfigured()).toBe(false);
    },
  );

  it.each(configuredCases)(
    '$connector.name throws ConnectorNotConfiguredError rather than fabricating data when unconfigured',
    async ({ connector }) => {
      for (const envVar of connector.configEnvVars) {
        delete process.env[envVar];
      }
      // No fetch mock installed at all -- if the connector tried to invent data instead of
      // checking configuration first, this test would fail on a real network call in CI.
      await expect(connector.fetchItems()).rejects.toBeInstanceOf(ConnectorNotConfiguredError);
    },
  );
});

describe('static no-fabrication guarantee', () => {
  it('no connector source file contains a synthetic/randomized data path', async () => {
    const connectorsDir = join(import.meta.dirname, '..', 'connectors');
    const files = (await readdir(connectorsDir)).filter(
      (file) => file.endsWith('.ts') && !file.endsWith('.test.ts') && file !== 'index.ts',
    );
    expect(files.length).toBeGreaterThanOrEqual(allConnectors.length);

    const forbiddenPatterns = [/Math\.random\s*\(/, /faker\./i, /new Date\(\)\.toISOString\(\)/];
    for (const file of files) {
      const source = await readFile(join(connectorsDir, file), 'utf-8');
      for (const pattern of forbiddenPatterns) {
        expect(source, `${file} must not match ${pattern}`).not.toMatch(pattern);
      }
    }
  });
});
