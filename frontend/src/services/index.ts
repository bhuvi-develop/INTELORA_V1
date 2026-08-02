/**
 * Data access layer.
 *
 * Everything that talks to the platform lives here. Components never import
 * from this directory directly — they consume hooks, which is what keeps the
 * source of data invisible to the presentation layer.
 */

export {
  alertsApi,
  assetsApi,
  dashboardApi,
  intelligenceApi,
  platformApi,
  telemetryApi,
} from './api'
export type { AlertListParams, AssetListParams, TelemetryHistoryParams } from './api'
export { addErrorInterceptor, addRequestInterceptor, download, http, toQuery } from './http'
export { liveStream } from './live-stream'
export type { ConnectionState, LiveMessage, LiveMessageType } from './live-stream'
