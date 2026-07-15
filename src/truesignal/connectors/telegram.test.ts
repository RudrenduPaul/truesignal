import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { telegramConnector } from './telegram.js';
import { ConnectorNotConfiguredError } from '../types.js';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

let tempDir: string;
const originalToken = process.env['TELEGRAM_BOT_TOKEN'];

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), 'truesignal-telegram-test-'));
  process.env['TRUESIGNAL_CACHE_DIR'] = tempDir;
});

afterEach(async () => {
  vi.unstubAllGlobals();
  if (originalToken === undefined) delete process.env['TELEGRAM_BOT_TOKEN'];
  else process.env['TELEGRAM_BOT_TOKEN'] = originalToken;
  await rm(tempDir, { recursive: true, force: true });
});

describe('telegramConnector', () => {
  it('is unconfigured with no bot token, and throws rather than fetching', async () => {
    delete process.env['TELEGRAM_BOT_TOKEN'];
    expect(telegramConnector.isConfigured()).toBe(false);
    await expect(telegramConnector.fetchItems()).rejects.toBeInstanceOf(
      ConnectorNotConfiguredError,
    );
  });

  it('uses the official getUpdates Bot API method, never t.me/s/* scraping', async () => {
    process.env['TELEGRAM_BOT_TOKEN'] = 'fake-token';
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        ok: true,
        result: [
          {
            update_id: 1,
            channel_post: {
              message_id: 5,
              date: 1750000000,
              chat: { id: 111, title: 'Example Channel', username: 'examplechan' },
              text: 'A real channel post',
            },
          },
        ],
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const items = await telegramConnector.fetchItems();

    expect(items).toHaveLength(1);
    expect(items[0]?.url).toBe('https://t.me/examplechan/5');
    const calledUrl = (fetchMock.mock.calls[0]?.[0] as string | URL).toString();
    expect(calledUrl).toContain('api.telegram.org');
    expect(calledUrl).toContain('getUpdates');
    expect(calledUrl).not.toContain('t.me/s/');
  });

  it('skips messages from chats with no public username rather than fabricating a link', async () => {
    process.env['TELEGRAM_BOT_TOKEN'] = 'fake-token';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          ok: true,
          result: [
            {
              update_id: 1,
              message: {
                message_id: 9,
                date: 1750000000,
                chat: { id: 222, title: 'Private group' },
                text: 'private message with no public username',
              },
            },
          ],
        }),
      ),
    );
    const items = await telegramConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('skips messages with no text or caption', async () => {
    process.env['TELEGRAM_BOT_TOKEN'] = 'fake-token';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          ok: true,
          result: [
            {
              update_id: 1,
              channel_post: { message_id: 9, date: 1750000000, chat: { id: 1, username: 'chan' } },
            },
          ],
        }),
      ),
    );
    const items = await telegramConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('falls back rather than fabricating when the Bot API reports ok: false', async () => {
    process.env['TELEGRAM_BOT_TOKEN'] = 'fake-token';
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ ok: false, description: 'Unauthorized' })),
    );
    const items = await telegramConnector.fetchItems();
    expect(items).toEqual([]);
  });

  it('truncates very long message text rather than emitting an unbounded title', async () => {
    process.env['TELEGRAM_BOT_TOKEN'] = 'fake-token';
    const longText = 'a'.repeat(200);
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({
          ok: true,
          result: [
            {
              update_id: 1,
              channel_post: {
                message_id: 1,
                date: 1750000000,
                chat: { id: 1, username: 'chan' },
                text: longText,
              },
            },
          ],
        }),
      ),
    );
    const [item] = await telegramConnector.fetchItems();
    expect(item?.title.length).toBeLessThanOrEqual(120);
    expect(item?.title.endsWith('…')).toBe(true);
  });
});
