import { cisaKevConnector } from './cisa-kev.js';
import { cloudflareRadarConnector } from './cloudflare-radar.js';
import { redditConnector } from './reddit.js';
import { telegramConnector } from './telegram.js';
import { gdeltConnector } from './gdelt.js';
import type { Connector } from '../types.js';

/**
 * Every connector this build ships, in a fixed order. Adding a new source is: implement
 * {@link Connector} in a new file in this directory, then add it here -- nothing else in the CLI
 * or provenance layer needs to change. See CONTRIBUTING.md.
 */
export const allConnectors: readonly Connector[] = [
  cisaKevConnector,
  cloudflareRadarConnector,
  redditConnector,
  telegramConnector,
  gdeltConnector,
];

export function getConnector(name: string): Connector | undefined {
  return allConnectors.find((connector) => connector.name === name);
}

export {
  cisaKevConnector,
  cloudflareRadarConnector,
  redditConnector,
  telegramConnector,
  gdeltConnector,
};
