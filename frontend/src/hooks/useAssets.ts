/**
 * Asset hooks.
 *
 * Two distinct views: the registry (identity and telemetry capability) and the
 * business model (the unified contract every dashboard surface binds to).
 * Choosing between them is the single most important call a component makes —
 * anything on the Cockpit uses the business model.
 */

import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/constants/query-keys'
import { assetsApi, type AssetListParams } from '@/services/api'
import type {
  Asset,
  AssetBusinessModel,
  AssetType,
  AssetTypeSummary,
  HealthState,
  Page,
  TelemetryReading,
} from '@/types'

/** Paginated registry, for the asset table. */
export function useAssetList(params: AssetListParams) {
  return useQuery<Page<Asset>>({
    queryKey: queryKeys.assets.list(params as Record<string, unknown>),
    queryFn: () => assetsApi.list(params),
    staleTime: 20_000,
    // Keeps the previous page visible while the next loads, so sorting and
    // paging never flash an empty table.
    placeholderData: (previous) => previous,
  })
}

/** The fleet in the unified business model. */
export function useAssetBusinessModels(assetType?: AssetType, health?: HealthState) {
  return useQuery<AssetBusinessModel[]>({
    queryKey: queryKeys.assets.business(assetType, health),
    queryFn: () => assetsApi.business(assetType, health),
    staleTime: 15_000,
    refetchInterval: 20_000,
  })
}

/** Per-category roll-up, backing the three premium asset cards. */
export function useAssetSummaries() {
  return useQuery<AssetTypeSummary[]>({
    queryKey: queryKeys.assets.summary(),
    queryFn: assetsApi.summary,
    staleTime: 60_000,
  })
}

export function useAsset(assetId: string | undefined) {
  return useQuery<Asset>({
    queryKey: queryKeys.assets.detail(assetId ?? ''),
    queryFn: () => assetsApi.detail(assetId as string),
    enabled: Boolean(assetId),
  })
}

export function useAssetBusiness(assetId: string | undefined) {
  return useQuery<AssetBusinessModel>({
    queryKey: [...queryKeys.assets.detail(assetId ?? ''), 'business'],
    queryFn: () => assetsApi.detailBusiness(assetId as string),
    enabled: Boolean(assetId),
    refetchInterval: 5_000,
  })
}

/**
 * Latest raw reading for one asset.
 *
 * The business model deliberately excludes category-specific channels — that
 * is what makes it uniform. Battery level, charge phase and conditioned-space
 * temperature therefore come from the reading itself, and only the asset
 * detail view needs them.
 */
export function useAssetTelemetry(assetId: string | undefined) {
  return useQuery<TelemetryReading | null>({
    queryKey: [...queryKeys.assets.detail(assetId ?? ''), 'telemetry'],
    queryFn: () => assetsApi.latestTelemetry(assetId as string),
    enabled: Boolean(assetId),
    refetchInterval: 5_000,
  })
}
