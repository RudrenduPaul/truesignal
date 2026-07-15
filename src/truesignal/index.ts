/** Library entry point -- import truesignal's connectors and provenance layer programmatically. */
export type { Connector, FeedItem, ItemStatus } from './types.js';
export { ConnectorNotConfiguredError } from './types.js';
export { allConnectors, getConnector } from './connectors/index.js';
export {
  fetchWithFallback,
  stampLive,
  stampFallback,
  readCache,
  writeCache,
  getCacheDir,
} from './provenance/index.js';
