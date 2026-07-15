/**
 * Reddit connector -- pulls new posts from a security/OSINT-relevant subreddit via Reddit's
 * official OAuth API (application-only "client_credentials" grant, read-only, public data).
 *
 * Requires a free Reddit developer app (script or web app type) via REDDIT_CLIENT_ID and
 * REDDIT_CLIENT_SECRET. Never scrapes the unauthenticated `.json` endpoints -- that path violates
 * Reddit's API terms of service, which is exactly the failure mode this connector exists to not
 * repeat (see Crucix issue #108 in the public issue tracker).
 */
import { fetchWithFallback, type UnstampedItem } from '../provenance/index.js';
import { ConnectorNotConfiguredError, type Connector } from '../types.js';

export const REDDIT_TOKEN_URL = 'https://www.reddit.com/api/v1/access_token';
export const REDDIT_API_BASE = 'https://oauth.reddit.com';
export const REDDIT_DEFAULT_SUBREDDIT = 'netsec';
export const REDDIT_MAX_ITEMS = 25;
export const REDDIT_USER_AGENT = 'truesignal-cli/0.1 (by /u/truesignal-oss)';

const CLIENT_ID_ENV_VAR = 'REDDIT_CLIENT_ID';
const CLIENT_SECRET_ENV_VAR = 'REDDIT_CLIENT_SECRET';
const SUBREDDIT_ENV_VAR = 'REDDIT_SUBREDDIT';

interface RedditTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface RedditPost {
  id: string;
  title: string;
  permalink: string;
  created_utc: number;
  subreddit: string;
}

interface RedditListingResponse {
  data?: {
    children?: { data: RedditPost }[];
  };
}

function isConfigured(): boolean {
  return Boolean(
    process.env[CLIENT_ID_ENV_VAR]?.trim() && process.env[CLIENT_SECRET_ENV_VAR]?.trim(),
  );
}

function targetSubreddit(): string {
  return process.env[SUBREDDIT_ENV_VAR]?.trim() || REDDIT_DEFAULT_SUBREDDIT;
}

async function fetchAccessToken(clientId: string, clientSecret: string): Promise<string> {
  const basicAuth = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
  const response = await fetch(REDDIT_TOKEN_URL, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${basicAuth}`,
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': REDDIT_USER_AGENT,
    },
    body: 'grant_type=client_credentials',
  });
  if (!response.ok) {
    throw new Error(`Reddit token endpoint returned HTTP ${response.status}`);
  }
  const data = (await response.json()) as RedditTokenResponse;
  if (!data.access_token) {
    throw new Error('Reddit token endpoint did not return an access_token');
  }
  return data.access_token;
}

function toUnstampedItem(post: RedditPost): UnstampedItem {
  return {
    id: `reddit:${post.id}`,
    source: 'reddit',
    title: post.title,
    url: `https://reddit.com${post.permalink}`,
    timestamp: new Date(post.created_utc * 1000).toISOString(),
    summary: `r/${post.subreddit}`,
  };
}

async function fetchLive(): Promise<UnstampedItem[]> {
  const clientId = process.env[CLIENT_ID_ENV_VAR];
  const clientSecret = process.env[CLIENT_SECRET_ENV_VAR];
  if (!clientId || !clientSecret) {
    throw new ConnectorNotConfiguredError('reddit');
  }

  const token = await fetchAccessToken(clientId, clientSecret);
  const url = new URL(`${REDDIT_API_BASE}/r/${targetSubreddit()}/new`);
  url.searchParams.set('limit', String(REDDIT_MAX_ITEMS));

  const response = await fetch(url.toString(), {
    headers: {
      Authorization: `Bearer ${token}`,
      'User-Agent': REDDIT_USER_AGENT,
    },
  });
  if (!response.ok) {
    throw new Error(`Reddit listing API returned HTTP ${response.status}`);
  }
  const data = (await response.json()) as RedditListingResponse;
  const children = data.data?.children ?? [];
  return children.map((child) => toUnstampedItem(child.data));
}

export const redditConnector: Connector = {
  name: 'reddit',
  label: 'Reddit',
  requiresConfig: true,
  configEnvVars: [CLIENT_ID_ENV_VAR, CLIENT_SECRET_ENV_VAR],
  isConfigured,
  async fetchItems() {
    if (!isConfigured()) {
      throw new ConnectorNotConfiguredError('reddit');
    }
    return fetchWithFallback('reddit', fetchLive);
  },
};
