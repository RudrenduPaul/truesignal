/**
 * Cloudflare Radar connector -- pulls recent global traffic anomalies from the official Radar
 * API. Requires a free Cloudflare API token (radar read scope) via the CLOUDFLARE_RADAR_API_TOKEN
 * environment variable. Docs: https://developers.cloudflare.com/radar/
 */
import { fetchWithFallback, type UnstampedItem } from '../provenance/index.js';
import { ConnectorNotConfiguredError, type Connector } from '../types.js';

export const CLOUDFLARE_RADAR_API_URL =
  'https://api.cloudflare.com/client/v4/radar/traffic_anomalies';
export const CLOUDFLARE_RADAR_MAX_ITEMS = 25;

const TOKEN_ENV_VAR = 'CLOUDFLARE_RADAR_API_TOKEN';

interface RadarAsnDetails {
  asn?: number;
  name?: string;
}

interface RadarLocationDetails {
  name?: string;
}

interface RadarTrafficAnomaly {
  uuid: string;
  startDate: string;
  type?: string;
  asnDetails?: RadarAsnDetails;
  locationDetails?: RadarLocationDetails;
}

interface RadarResponse {
  success: boolean;
  result?: {
    trafficAnomalies?: RadarTrafficAnomaly[];
  };
}

function isConfigured(): boolean {
  return Boolean(process.env[TOKEN_ENV_VAR]?.trim());
}

function toUnstampedItem(anomaly: RadarTrafficAnomaly): UnstampedItem {
  const subject = anomaly.asnDetails?.name ?? anomaly.locationDetails?.name ?? 'Unknown network';
  const anomalyType = anomaly.type ?? 'traffic anomaly';
  return {
    id: `cloudflare-radar:${anomaly.uuid}`,
    source: 'cloudflare-radar',
    title: `${subject}: ${anomalyType}`,
    url: `https://radar.cloudflare.com/anomalies/${anomaly.uuid}`,
    timestamp: new Date(anomaly.startDate).toISOString(),
    ...(anomaly.asnDetails?.asn ? { summary: `AS${anomaly.asnDetails.asn}` } : {}),
  };
}

async function fetchLive(): Promise<UnstampedItem[]> {
  const token = process.env[TOKEN_ENV_VAR];
  if (!token) {
    throw new ConnectorNotConfiguredError('cloudflare-radar');
  }

  const url = new URL(CLOUDFLARE_RADAR_API_URL);
  url.searchParams.set('limit', String(CLOUDFLARE_RADAR_MAX_ITEMS));

  const response = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Cloudflare Radar API returned HTTP ${response.status}`);
  }
  const data = (await response.json()) as RadarResponse;
  if (!data.success) {
    throw new Error('Cloudflare Radar API reported success: false');
  }
  const anomalies = data.result?.trafficAnomalies ?? [];
  return anomalies.map(toUnstampedItem);
}

export const cloudflareRadarConnector: Connector = {
  name: 'cloudflare-radar',
  label: 'Cloudflare Radar',
  requiresConfig: true,
  configEnvVars: [TOKEN_ENV_VAR],
  isConfigured,
  async fetchItems() {
    if (!isConfigured()) {
      throw new ConnectorNotConfiguredError('cloudflare-radar');
    }
    return fetchWithFallback('cloudflare-radar', fetchLive);
  },
};
