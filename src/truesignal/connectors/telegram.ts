/**
 * Telegram connector -- pulls recent channel posts via the official Telegram Bot API's
 * `getUpdates` method. Requires a free bot token (from @BotFather) via TELEGRAM_BOT_TOKEN.
 *
 * Never scrapes `t.me/s/*` with a spoofed User-Agent -- that path violates Telegram's terms of
 * service, which is exactly the failure mode this connector exists to not repeat (see Crucix
 * issue #110 in the public issue tracker).
 *
 * Real API constraint, not a workaround: the Bot API only surfaces updates for chats the bot has
 * been added to as a member/admin, via long-polling `getUpdates`. Posts from a chat with no
 * public @username are skipped rather than linked with a fabricated URL -- every item this
 * connector emits must have a real, dereferenceable t.me link.
 */
import { fetchWithFallback, type UnstampedItem } from '../provenance/index.js';
import { ConnectorNotConfiguredError, type Connector } from '../types.js';

export const TELEGRAM_API_BASE = 'https://api.telegram.org';
export const TELEGRAM_MAX_ITEMS = 25;
const TITLE_MAX_LENGTH = 120;

const TOKEN_ENV_VAR = 'TELEGRAM_BOT_TOKEN';

interface TelegramChat {
  id: number;
  title?: string;
  username?: string;
}

interface TelegramMessage {
  message_id: number;
  date: number;
  chat: TelegramChat;
  text?: string;
  caption?: string;
}

interface TelegramUpdate {
  update_id: number;
  channel_post?: TelegramMessage;
  message?: TelegramMessage;
}

interface TelegramGetUpdatesResponse {
  ok: boolean;
  description?: string;
  result?: TelegramUpdate[];
}

function isConfigured(): boolean {
  return Boolean(process.env[TOKEN_ENV_VAR]?.trim());
}

function truncate(text: string): string {
  return text.length > TITLE_MAX_LENGTH ? `${text.slice(0, TITLE_MAX_LENGTH - 1)}…` : text;
}

function toUnstampedItem(message: TelegramMessage): UnstampedItem | null {
  const username = message.chat.username;
  const body = message.text ?? message.caption;
  // Only chats with a public username produce a real, dereferenceable link -- private chats are
  // skipped rather than given a fabricated URL.
  if (!username || !body) {
    return null;
  }
  return {
    id: `telegram:${message.chat.id}:${message.message_id}`,
    source: 'telegram',
    title: truncate(body),
    url: `https://t.me/${username}/${message.message_id}`,
    timestamp: new Date(message.date * 1000).toISOString(),
    ...(message.chat.title !== undefined ? { summary: message.chat.title } : {}),
  };
}

async function fetchLive(): Promise<UnstampedItem[]> {
  const token = process.env[TOKEN_ENV_VAR];
  if (!token) {
    throw new ConnectorNotConfiguredError('telegram');
  }

  const url = new URL(`${TELEGRAM_API_BASE}/bot${token}/getUpdates`);
  url.searchParams.set('limit', String(TELEGRAM_MAX_ITEMS));

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`Telegram Bot API returned HTTP ${response.status}`);
  }
  const data = (await response.json()) as TelegramGetUpdatesResponse;
  if (!data.ok) {
    throw new Error(`Telegram Bot API error: ${data.description ?? 'unknown error'}`);
  }
  const updates = data.result ?? [];
  const items: UnstampedItem[] = [];
  for (const update of updates) {
    const message = update.channel_post ?? update.message;
    if (!message) continue;
    const item = toUnstampedItem(message);
    if (item) items.push(item);
  }
  return items;
}

export const telegramConnector: Connector = {
  name: 'telegram',
  label: 'Telegram',
  requiresConfig: true,
  configEnvVars: [TOKEN_ENV_VAR],
  isConfigured,
  async fetchItems() {
    if (!isConfigured()) {
      throw new ConnectorNotConfiguredError('telegram');
    }
    return fetchWithFallback('telegram', fetchLive);
  },
};
