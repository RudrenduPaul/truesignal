/**
 * CISA Known Exploited Vulnerabilities (KEV) catalog connector.
 *
 * Public JSON feed, no API key required -- works with zero configuration. Source:
 * https://www.cisa.gov/known-exploited-vulnerabilities-catalog
 */
import { fetchWithFallback, type UnstampedItem } from '../provenance/index.js';
import type { Connector } from '../types.js';

export const CISA_KEV_FEED_URL =
  'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json';

/** Cap on how many of the most recently added vulnerabilities a single feed pull returns. */
export const CISA_KEV_MAX_ITEMS = 25;

interface CisaKevVulnerability {
  cveID: string;
  vendorProject: string;
  product: string;
  vulnerabilityName: string;
  dateAdded: string;
  shortDescription: string;
}

interface CisaKevResponse {
  vulnerabilities: CisaKevVulnerability[];
}

function toUnstampedItem(vuln: CisaKevVulnerability): UnstampedItem | null {
  // dateAdded from CISA is a bare date ("2026-07-10"); treat it as midnight UTC so it is a real,
  // parseable ISO-8601 instant rather than a fabricated time-of-day. A single record with a
  // missing or malformed dateAdded is skipped rather than thrown -- one bad record in an
  // otherwise-good batch must not take down every other real item alongside it.
  const parsed = new Date(`${vuln.dateAdded}T00:00:00.000Z`);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return {
    id: `cisa-kev:${vuln.cveID}`,
    source: 'cisa-kev',
    title: `${vuln.cveID}: ${vuln.vulnerabilityName}`,
    url: `https://nvd.nist.gov/vuln/detail/${vuln.cveID}`,
    timestamp: parsed.toISOString(),
    summary: `${vuln.vendorProject} ${vuln.product} -- ${vuln.shortDescription}`,
  };
}

async function fetchLive(): Promise<UnstampedItem[]> {
  const response = await fetch(CISA_KEV_FEED_URL);
  if (!response.ok) {
    throw new Error(`CISA-KEV feed returned HTTP ${response.status}`);
  }
  const data = (await response.json()) as CisaKevResponse;
  if (!Array.isArray(data.vulnerabilities)) {
    throw new Error('CISA-KEV feed returned an unexpected shape');
  }
  return data.vulnerabilities
    .slice()
    .sort((a, b) => (a.dateAdded < b.dateAdded ? 1 : -1))
    .slice(0, CISA_KEV_MAX_ITEMS)
    .map(toUnstampedItem)
    .filter((item): item is UnstampedItem => item !== null);
}

export const cisaKevConnector: Connector = {
  name: 'cisa-kev',
  label: 'CISA Known Exploited Vulnerabilities',
  requiresConfig: false,
  configEnvVars: [],
  isConfigured(): boolean {
    return true;
  },
  async fetchItems() {
    return fetchWithFallback('cisa-kev', fetchLive);
  },
};
