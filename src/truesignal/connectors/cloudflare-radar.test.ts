import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cloudflareRadarConnector } from './cloudflare-radar.js';
import { ConnectorNotConfiguredError } from '../types.js';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

let tempDir: string;
const originalToken = process.env['CLOUDFLARE_RADAR_API_TOKEN'];

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-radar-test-'));
  process.env['TRUESIGNAL_CACHE_DIR'] = tempDir;
});

afterEach(async () => {
  vi.unstubAllGlobals();
  if (originalToken === undefined) delete process.env['CLOUDFLARE_RADAR_API_TOKEN'];
  else process.env['CLOUDFLARE_RADAR_API_TOKEN'] = originalToken;
  await rm(tempDir, { recursive: true, force: true });
});

describe('cloudflareRadarConnector', () => {
  it('reports not configured with no token, and throws rather than fetching', async () => {
    delete process.env['CLOUDFLARE_RADAR_API_TOKEN'];
    expect(cloudflareRadarConnector.isConfigured()).toBe(false);
    await expect(cloudflareRadarConnector.fetchItems()).rejects.toBeInstanceOf(
      ConnectorNotConfiguredError,
    );
  });

  it('reports configured once the token env var is set', () => {
    process.env['CLOUDFLARE_RADAR_API_TOKEN'] = 'fake-token';
    expect(cloudflareRadarConnector.isConfigured()).toBe(true);
  });

  it('treats a blank token as unconfigured', () => {
    process.env['CLOUDFLARE_RADAR_API_TOKEN'] = '   ';
    expect(cloudflareRadarConnector.isConfigured()).toBe(false);
  });

  it('sends the token as a real Bearer Authorization header', async () => {
    process.env['CLOUDFLARE_RADAR_API_TOKEN'] = 'fake-token-value';
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: true, result: { trafficAnomalies: [] } }));
    vi.stubGlobal('fetch', fetchMock);

    await cloudflareRadarConnector.fetchItems();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)['Authorization']).toBe(
      'Bearer fake-token-value',
    );
  });

  it('falls back to empty on success: false rather than trusting a malformed live payload', async () => {
    process.env['CLOUDFLARE_RADAR_API_TOKEN'] = 'fake-token';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ success: false })));
    const items = await cloudflareRadarConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('uses the location name when no ASN details are present', async () => {
    process.env['CLOUDFLARE_RADAR_API_TOKEN'] = 'fake-token';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          success: true,
          result: {
            trafficAnomalies: [
              {
                uuid: 'a1',
                startDate: '2026-02-01T00:00:00Z',
                type: 'outage',
                locationDetails: { name: 'Testland' },
              },
            ],
          },
        }),
      ),
    );
    const [item] = await cloudflareRadarConnector.fetchItems();
    expect(item?.title).toContain('Testland');
    expect(item?.summary).toBeUndefined();
  });
});
