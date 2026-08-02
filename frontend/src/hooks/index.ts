/** Reusable behaviour. Components stay declarative; logic lives here. */

export { useBoot, useLive, useSidebar, useTheme } from './useAppContext'
export { useClock } from './useClock'
export { useCountUp } from './useCountUp'
export { useDataTable } from './useDataTable'
export type { Column } from './useDataTable'
export { useIsDesktop, useIsMobile, useIsTablet, useMediaQuery } from './useMediaQuery'
export { usePrefersReducedMotion } from './usePrefersReducedMotion'

export {
  useAsset,
  useAssetBusiness,
  useAssetBusinessModels,
  useAssetList,
  useAssetSummaries,
  useAssetTelemetry,
} from './useAssets'
export {
  useAlert,
  useAlertList,
  useAlertSummary,
  useDismissAlert,
  useUpdateAlert,
} from './useAlerts'
export {
  useChartBundle,
  useCockpitOverview,
  useIntelligenceSummary,
  useKpis,
  useRecentTelemetry,
} from './useDashboard'
export {
  useAnomalies,
  useAnomalySummary,
  useApmRanking,
  useApmResults,
  useApmSummary,
  useAssetAnomalies,
  useMaintenanceSchedule,
  useOee,
  useOeeHistory,
  usePredictions,
  usePredictiveSummary,
  usePreventiveSummary,
  useRecommendations,
  useRunIntelligence,
} from './useIntelligence'
export {
  useExportReport,
  usePlatformHealth,
  useReports,
  useSaveSettings,
  useSettings,
  useTelemetryHistory,
  useTwinControl,
  useTwinDevices,
  useTwinStatus,
} from './usePlatform'
