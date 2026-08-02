import { lazy } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import { AppShell } from '@/layouts/AppShell'
import { ROUTES } from '@/constants/navigation'

/**
 * Route table.
 *
 * Every page is code-split. The performance mandate requires lazy loading, and
 * it matters here specifically: the Cockpit pulls in ECharts, while Settings
 * and Reports do not, so a user who never opens a chart-heavy module never
 * downloads the chart library.
 *
 * The Cockpit is the exception — it is the landing page, so splitting it would
 * add a round trip to the very first paint the user sees after the splash.
 */

import { CockpitPage } from '@/pages/CockpitPage'

const AnomalyPage = lazy(() => import('@/pages/AnomalyPage'))
const PredictivePage = lazy(() => import('@/pages/PredictivePage'))
const OeePage = lazy(() => import('@/pages/OeePage'))
const ApmPage = lazy(() => import('@/pages/ApmPage'))
const AlertsPage = lazy(() => import('@/pages/AlertsPage'))
const AlertDetailPage = lazy(() => import('@/pages/AlertDetailPage'))
const AssetsPage = lazy(() => import('@/pages/AssetsPage'))
const AssetDetailPage = lazy(() => import('@/pages/AssetDetailPage'))
const EnergyPage = lazy(() => import('@/pages/EnergyPage'))
const ReportsPage = lazy(() => import('@/pages/ReportsPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <CockpitPage /> },

      /* Device Intelligence */
      { path: 'anomaly', element: <AnomalyPage /> },
      { path: 'predictive', element: <PredictivePage /> },
      { path: 'assets', element: <AssetsPage /> },
      { path: 'assets/:assetId', element: <AssetDetailPage /> },

      /* Business Intelligence */
      { path: 'apm', element: <ApmPage /> },
      { path: 'oee', element: <OeePage /> },
      { path: 'energy', element: <EnergyPage /> },

      /* Operations */
      { path: 'alerts', element: <AlertsPage /> },
      { path: 'alerts/:alertId', element: <AlertDetailPage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'settings', element: <SettingsPage /> },

      /* Legacy and convenience redirects. */
      { path: 'cockpit', element: <Navigate to={ROUTES.cockpit} replace /> },
      { path: 'dashboard', element: <Navigate to={ROUTES.cockpit} replace /> },

      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
