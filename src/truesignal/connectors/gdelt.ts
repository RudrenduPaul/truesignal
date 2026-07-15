/**
 * GDELT connector -- pulls recent OSINT/security-relevant news coverage from the GDELT 2.0 DOC
 * API. Public API, no key required -- works with zero configuration.
 * Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
 */
import { fetchWithFallback, type UnstampedItem } from '../provenance/index.js';
import type { Connector } from '../types.js';

export const GDELT_API_URL = 'https://api.gdeltproject.org/api/v2/doc/doc';

/** Default query: security/OSINT-relevant English-language coverage. */
export const GDELT_DEFAULT_QUERY =
  '(cyberattack OR vulnerability OR "data breach") sourcelang:english';

export const GDELT_MAX_RECORDS = 25;

interface GdeltArticle {
  url: string;
  title: string;
  seendate: string;
  domain: string;
  sourcecountry?: string;
}

interface GdeltResponse {
  articles?: GdeltArticle[];
}

function parseGdeltDate(seendate: string): string {
  // GDELT returns "YYYYMMDDTHHMMSSZ" -- a real compact ISO-8601 basic-format instant.
  const match = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(seendate);
  if (!match) {
    throw new Error(`Unrecognized GDELT seendate format: ${seendate}`);
  }
  const [, year, month, day, hour, minute, second] = match;
  return new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}.000Z`).toISOString();
}

function toUnstampedItem(article: GdeltArticle): UnstampedItem {
  return {
    id: `gdelt:${article.url}`,
    source: 'gdelt',
    title: article.title,
    url: article.url,
    timestamp: parseGdeltDate(article.seendate),
    summary: article.sourcecountry
      ? `${article.domain} (${article.sourcecountry})`
      : article.domain,
  };
}

async function fetchLive(): Promise<UnstampedItem[]> {
  const url = new URL(GDELT_API_URL);
  url.searchParams.set('query', GDELT_DEFAULT_QUERY);
  url.searchParams.set('mode', 'artlist');
  url.searchParams.set('format', 'json');
  url.searchParams.set('maxrecords', String(GDELT_MAX_RECORDS));
  url.searchParams.set('sort', 'datedesc');

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`GDELT API returned HTTP ${response.status}`);
  }
  const data = (await response.json()) as GdeltResponse;
  const articles = data.articles ?? [];
  return articles.map(toUnstampedItem);
}

export const gdeltConnector: Connector = {
  name: 'gdelt',
  label: 'GDELT',
  requiresConfig: false,
  configEnvVars: [],
  isConfigured(): boolean {
    return true;
  },
  async fetchItems() {
    return fetchWithFallback('gdelt', fetchLive);
  },
};
