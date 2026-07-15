import { describe, expect, it } from 'vitest';
import {
  ExitCode,
  formatFeedItemHuman,
  formatInitReport,
  getConnectorStatuses,
  parseItemId,
  runFeed,
  runVerify,
  selectConnectors,
} from './cli-helpers.js';
import type { Connector, FeedItem } from './types.js';

function makeConnector(overrides: Partial<Connector> & { name: string }): Connector {
  return {
    label: overrides.name,
    requiresConfig: false,
    configEnvVars: [],
    isConfigured: () => true,
    fetchItems: async () => [],
    ...overrides,
  };
}

const liveItem: FeedItem = {
  id: 'cisa-kev:CVE-2026-00001',
  source: 'cisa-kev',
  title: 'Sample CVE',
  url: 'https://nvd.nist.gov/vuln/detail/CVE-2026-00001',
  timestamp: '2026-07-01T00:00:00.000Z',
  status: 'live',
};

const fallbackItem: FeedItem = {
  ...liveItem,
  id: 'gdelt:https://example.com/a',
  source: 'gdelt',
  status: 'fallback',
  fallbackAgeSeconds: 3661,
};

describe('ExitCode', () => {
  it('assigns each meaning a distinct code', () => {
    const values = Object.values(ExitCode);
    expect(new Set(values).size).toBe(values.length);
  });
});

describe('getConnectorStatuses / formatInitReport', () => {
  it('reports zero-config connectors as ready with no missing env vars', () => {
    const connector = makeConnector({ name: 'cisa-kev', requiresConfig: false });
    const [status] = getConnectorStatuses([connector]);
    expect(status).toMatchObject({
      name: 'cisa-kev',
      requiresConfig: false,
      configured: true,
      missingEnvVars: [],
    });
  });

  it('reports an unconfigured connector with its missing env vars', () => {
    const connector = makeConnector({
      name: 'reddit',
      requiresConfig: true,
      configEnvVars: ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET'],
      isConfigured: () => false,
    });
    const [status] = getConnectorStatuses([connector]);
    expect(status?.missingEnvVars).toEqual(['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET']);
  });

  it('formatInitReport lists every connector and a ready-count summary', () => {
    const ready = makeConnector({ name: 'cisa-kev' });
    const notReady = makeConnector({
      name: 'telegram',
      requiresConfig: true,
      configEnvVars: ['TELEGRAM_BOT_TOKEN'],
      isConfigured: () => false,
    });
    const report = formatInitReport(getConnectorStatuses([ready, notReady]));
    expect(report).toContain('cisa-kev');
    expect(report).toContain('telegram');
    expect(report).toContain('TELEGRAM_BOT_TOKEN');
    expect(report).toContain('1/2 connectors ready.');
  });

  it('formatInitReport warns when nothing at all is ready', () => {
    const notReady = makeConnector({
      name: 'telegram',
      requiresConfig: true,
      configEnvVars: ['TELEGRAM_BOT_TOKEN'],
      isConfigured: () => false,
    });
    const report = formatInitReport(getConnectorStatuses([notReady]));
    expect(report).toContain('No connectors are usable');
  });
});

describe('selectConnectors', () => {
  const ready = makeConnector({ name: 'cisa-kev' });
  const configured = makeConnector({
    name: 'cloudflare-radar',
    requiresConfig: true,
    isConfigured: () => true,
  });
  const notConfigured = makeConnector({
    name: 'telegram',
    requiresConfig: true,
    isConfigured: () => false,
  });
  const all = [ready, configured, notConfigured];

  it('with no filter, queries every configured-or-zero-config connector and skips the rest', () => {
    const selection = selectConnectors(all);
    expect(selection.toQuery.map((c) => c.name)).toEqual(['cisa-kev', 'cloudflare-radar']);
    expect(selection.skipped.map((c) => c.name)).toEqual(['telegram']);
    expect(selection.unknownSource).toBeUndefined();
  });

  it('with a valid --source filter, narrows to just that connector', () => {
    const selection = selectConnectors(all, 'cisa-kev');
    expect(selection.toQuery.map((c) => c.name)).toEqual(['cisa-kev']);
    expect(selection.skipped).toEqual([]);
  });

  it('with an unknown --source filter, reports unknownSource and queries nothing', () => {
    const selection = selectConnectors(all, 'not-a-real-source');
    expect(selection.unknownSource).toBe('not-a-real-source');
    expect(selection.toQuery).toEqual([]);
  });

  it('with --source naming an unconfigured connector, skips it rather than crashing', () => {
    const selection = selectConnectors(all, 'telegram');
    expect(selection.toQuery).toEqual([]);
    expect(selection.skipped.map((c) => c.name)).toEqual(['telegram']);
  });
});

describe('formatFeedItemHuman', () => {
  it('formats a live item with a real url and relative age', () => {
    const now = new Date('2026-07-01T00:05:00.000Z');
    const line = formatFeedItemHuman(liveItem, now);
    expect(line).toContain('[live]');
    expect(line).toContain(liveItem.url);
    expect(line).toContain('5m ago');
  });

  it('formats a fallback item with its honest cached age', () => {
    const now = new Date('2026-07-01T00:00:00.000Z');
    const line = formatFeedItemHuman(fallbackItem, now);
    expect(line).toContain('[fallback,');
    expect(line).toContain('1h old');
  });
});

describe('parseItemId', () => {
  it('splits a simple id on the first colon', () => {
    expect(parseItemId('cisa-kev:CVE-2026-00001')).toEqual({
      source: 'cisa-kev',
      nativeId: 'CVE-2026-00001',
    });
  });

  it('preserves colons inside the native id (e.g. a URL, or telegram chat:message)', () => {
    expect(parseItemId('gdelt:https://example.com/a')).toEqual({
      source: 'gdelt',
      nativeId: 'https://example.com/a',
    });
    expect(parseItemId('telegram:111:5')).toEqual({ source: 'telegram', nativeId: '111:5' });
  });

  it('returns null for a malformed id', () => {
    expect(parseItemId('no-colon-here')).toBeNull();
    expect(parseItemId(':missing-source')).toBeNull();
    expect(parseItemId('missing-native-id:')).toBeNull();
    expect(parseItemId('')).toBeNull();
  });
});

describe('runFeed', () => {
  it('aggregates items across every configured connector', async () => {
    const a = makeConnector({ name: 'a', fetchItems: async () => [liveItem] });
    const b = makeConnector({ name: 'b', fetchItems: async () => [fallbackItem] });
    const result = await runFeed([a, b]);
    expect(result.items).toEqual([liveItem, fallbackItem]);
    expect(result.failures).toEqual([]);
  });

  it('reports a failing connector without dropping items from the others', async () => {
    const good = makeConnector({ name: 'good', fetchItems: async () => [liveItem] });
    const bad = makeConnector({
      name: 'bad',
      fetchItems: async () => {
        throw new Error('boom');
      },
    });
    const result = await runFeed([good, bad]);
    expect(result.items).toEqual([liveItem]);
    expect(result.failures).toEqual([{ source: 'bad', error: 'boom' }]);
  });

  it('propagates an unknown --source as unknownSource without calling any connector', async () => {
    let called = false;
    const a = makeConnector({
      name: 'a',
      fetchItems: async () => {
        called = true;
        return [];
      },
    });
    const result = await runFeed([a], 'nonexistent');
    expect(result.unknownSource).toBe('nonexistent');
    expect(called).toBe(false);
  });
});

describe('runVerify', () => {
  it('reports invalid-id for a malformed item id', async () => {
    const result = await runVerify([], 'not-valid');
    expect(result.errorKind).toBe('invalid-id');
    expect(result.found).toBe(false);
  });

  it('reports unknown-source when no connector matches the id prefix', async () => {
    const result = await runVerify([makeConnector({ name: 'cisa-kev' })], 'unknown-source:123');
    expect(result.errorKind).toBe('unknown-source');
  });

  it('reports not-configured when the matching connector lacks required config', async () => {
    const connector = makeConnector({
      name: 'reddit',
      requiresConfig: true,
      isConfigured: () => false,
    });
    const result = await runVerify([connector], 'reddit:abc123');
    expect(result.errorKind).toBe('not-configured');
  });

  it('reports network-error when fetchItems throws', async () => {
    const connector = makeConnector({
      name: 'cisa-kev',
      fetchItems: async () => {
        throw new Error('upstream down');
      },
    });
    const result = await runVerify([connector], 'cisa-kev:CVE-2026-00001');
    expect(result.errorKind).toBe('network-error');
    expect(result.errorMessage).toContain('upstream down');
  });

  it('reports found: false when the item is no longer in the feed', async () => {
    const connector = makeConnector({ name: 'cisa-kev', fetchItems: async () => [] });
    const result = await runVerify([connector], 'cisa-kev:CVE-2026-99999');
    expect(result.found).toBe(false);
    expect(result.errorKind).toBeUndefined();
  });

  it('reports full provenance details when the item is found live', async () => {
    const connector = makeConnector({ name: 'cisa-kev', fetchItems: async () => [liveItem] });
    const result = await runVerify([connector], liveItem.id);
    expect(result).toMatchObject({
      found: true,
      status: 'live',
      url: liveItem.url,
      timestamp: liveItem.timestamp,
    });
  });

  it('reports fallbackAgeSeconds when the item is found as a fallback', async () => {
    const connector = makeConnector({ name: 'gdelt', fetchItems: async () => [fallbackItem] });
    const result = await runVerify([connector], fallbackItem.id);
    expect(result).toMatchObject({ found: true, status: 'fallback', fallbackAgeSeconds: 3661 });
  });
});
