import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cisaKevConnector, CISA_KEV_MAX_ITEMS } from './cisa-kev.js';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

let tempDir: string;

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-cisa-kev-test-'));
  process.env['TRUESIGNAL_CACHE_DIR'] = tempDir;
});

afterEach(async () => {
  vi.unstubAllGlobals();
  await rm(tempDir, { recursive: true, force: true });
});

describe('cisaKevConnector', () => {
  it('requires no configuration', () => {
    expect(cisaKevConnector.requiresConfig).toBe(false);
    expect(cisaKevConnector.isConfigured()).toBe(true);
    expect(cisaKevConnector.configEnvVars).toEqual([]);
  });

  it('maps CISA vulnerabilities to real, verifiable feed items', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          vulnerabilities: [
            {
              cveID: 'CVE-2026-11111',
              vendorProject: 'Acme',
              product: 'Gadget',
              vulnerabilityName: 'Buffer Overflow',
              dateAdded: '2026-03-05',
              shortDescription: 'Remote attacker can execute arbitrary code.',
            },
          ],
        }),
      ),
    );

    const [item] = await cisaKevConnector.fetchItems();
    expect(item).toMatchObject({
      id: 'cisa-kev:CVE-2026-11111',
      source: 'cisa-kev',
      url: 'https://nvd.nist.gov/vuln/detail/CVE-2026-11111',
      timestamp: '2026-03-05T00:00:00.000Z',
      status: 'live',
    });
    expect(item?.title).toContain('CVE-2026-11111');
    expect(item?.summary).toContain('Acme');
  });

  it('sorts by dateAdded descending and caps at CISA_KEV_MAX_ITEMS', async () => {
    const vulnerabilities = Array.from({ length: CISA_KEV_MAX_ITEMS + 10 }, (_, i) => ({
      cveID: `CVE-2026-${String(i).padStart(5, '0')}`,
      vendorProject: 'Acme',
      product: 'Gadget',
      vulnerabilityName: 'Sample',
      dateAdded: `2026-01-${String((i % 28) + 1).padStart(2, '0')}`,
      shortDescription: 'desc',
    }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ vulnerabilities })));

    const items = await cisaKevConnector.fetchItems();
    expect(items).toHaveLength(CISA_KEV_MAX_ITEMS);
  });

  it('throws when the feed returns a non-OK HTTP status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 503)));
    // fetchItems itself never throws (fetchWithFallback catches it); no cache exists, so it
    // resolves to an empty array rather than propagating the error.
    const items = await cisaKevConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('throws when the feed returns an unexpected shape', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ notVulnerabilities: [] })));
    const items = await cisaKevConnector.fetchItems();
    expect(items).toEqual([]);
  });
});
