import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Boxes, BellRing, CornerDownLeft, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { popVariants, scrimVariants } from '@/animations/variants'
import { Badge } from '@/components/ui'
import { NAVIGATION } from '@/constants/navigation'
import { useAlertSummary } from '@/hooks/useAlerts'
import { useAssetBusinessModels } from '@/hooks/useAssets'
import { cn } from '@/utils/cn'
import { HEALTH_TONE, SEVERITY_TONE } from '@/utils/status'

/**
 * Global search.
 *
 * A command palette rather than a search page: on an operations platform the
 * user usually knows what they want and needs to reach it, not to browse a
 * result list. Covers modules, assets and alerts — the entity types the SSOT
 * specifies, minus users, which has no page yet.
 *
 * Fully keyboard-driven: ⌘K or Ctrl+K to open, arrows to move, Enter to go,
 * Escape to dismiss.
 */

interface Result {
  id: string
  group: 'Modules' | 'Assets' | 'Alerts'
  label: string
  hint: string
  path: string
  badge?: { text: string; tone: 'healthy' | 'warning' | 'critical' | 'primary' | 'neutral' }
}

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement | null>(null)

  // Only fetched while the palette is open — searching the fleet is not worth
  // a request on every page load.
  const { data: assets } = useAssetBusinessModels()
  const { data: alerts } = useAlertSummary()

  const results = useMemo<Result[]>(() => {
    const term = query.trim().toLowerCase()

    const modules: Result[] = NAVIGATION.flatMap((section) => section.items)
      .filter((item) => item.status === 'active')
      .filter(
        (item) =>
          !term ||
          item.label.toLowerCase().includes(term) ||
          item.description.toLowerCase().includes(term),
      )
      .map((item) => ({
        id: `module-${item.key}`,
        group: 'Modules' as const,
        label: item.label,
        hint: item.description,
        path: item.path,
      }))

    const assetResults: Result[] = !term
      ? []
      : (assets ?? [])
          .filter(
            (asset) =>
              asset.name.toLowerCase().includes(term) ||
              asset.asset_code.toLowerCase().includes(term),
          )
          .slice(0, 6)
          .map((asset) => ({
            id: `asset-${asset.asset_id}`,
            group: 'Assets' as const,
            label: asset.name,
            hint: `${asset.asset_code} · health ${asset.health_score.toFixed(0)}`,
            path: `/assets/${asset.asset_id}`,
            badge: { text: asset.health_state, tone: HEALTH_TONE[asset.health_state] },
          }))

    const alertResults: Result[] = !term
      ? []
      : (alerts?.recent ?? [])
          .filter(
            (alert) =>
              alert.title.toLowerCase().includes(term) ||
              (alert.asset_code ?? '').toLowerCase().includes(term),
          )
          .slice(0, 5)
          .map((alert) => ({
            id: `alert-${alert.id}`,
            group: 'Alerts' as const,
            label: alert.title,
            hint: alert.asset_code ?? 'Unassigned asset',
            path: `/alerts/${alert.id}`,
            badge: { text: alert.severity, tone: SEVERITY_TONE[alert.severity] },
          }))

    return [...modules, ...assetResults, ...alertResults]
  }, [query, assets, alerts])

  // Reset when reopened; a stale query from last time is disorienting.
  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      // Focus after the entry animation has begun, or the caret jumps.
      const timer = window.setTimeout(() => inputRef.current?.focus(), 40)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [open])

  useEffect(() => {
    setActive(0)
  }, [query])

  useEffect(() => {
    if (!open) return

    const handle = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onOpenChange(false)
      } else if (event.key === 'ArrowDown') {
        event.preventDefault()
        setActive((current) => Math.min(current + 1, results.length - 1))
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        setActive((current) => Math.max(current - 1, 0))
      } else if (event.key === 'Enter') {
        event.preventDefault()
        const target = results[active]
        if (target) {
          navigate(target.path)
          onOpenChange(false)
        }
      }
    }

    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [open, results, active, navigate, onOpenChange])

  let lastGroup: string | null = null

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            variants={scrimVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            className="fixed inset-0 z-[60] bg-[var(--intelora-scrim)] backdrop-blur-sm"
            onClick={() => onOpenChange(false)}
            aria-hidden
          />

          <motion.div
            variants={popVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            role="dialog"
            aria-modal
            aria-label="Global search"
            className={cn(
              'fixed top-[12vh] left-1/2 z-[61] w-[calc(100vw-32px)] max-w-2xl -translate-x-1/2',
              'glass-panel overflow-hidden',
            )}
          >
            <div className="flex items-center gap-3 border-b border-border px-5 py-4">
              <Search className="size-4 shrink-0 text-subtle" />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search modules, assets and alerts…"
                className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-subtle"
                aria-label="Search"
              />
              <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-subtle">
                ESC
              </kbd>
            </div>

            <div className="max-h-[52vh] overflow-y-auto p-2">
              {results.length === 0 ? (
                <p className="px-4 py-10 text-center text-sm text-subtle">
                  {query
                    ? `Nothing matches “${query}”.`
                    : 'Start typing to search the platform.'}
                </p>
              ) : (
                results.map((result, index) => {
                  const showGroup = result.group !== lastGroup
                  lastGroup = result.group

                  return (
                    <div key={result.id}>
                      {showGroup ? (
                        <p className="px-3 pt-3 pb-1.5 text-[10px] font-semibold tracking-[0.14em] text-subtle uppercase">
                          {result.group}
                        </p>
                      ) : null}

                      <button
                        type="button"
                        onMouseEnter={() => setActive(index)}
                        onClick={() => {
                          navigate(result.path)
                          onOpenChange(false)
                        }}
                        className={cn(
                          'flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left transition-colors',
                          index === active ? 'bg-primary-soft' : 'hover:bg-surface-sunken',
                        )}
                      >
                        <span className="grid size-8 shrink-0 place-items-center rounded-[8px] border border-border bg-surface-sunken text-subtle">
                          {result.group === 'Assets' ? (
                            <Boxes className="size-4" />
                          ) : result.group === 'Alerts' ? (
                            <BellRing className="size-4" />
                          ) : (
                            <ArrowRight className="size-4" />
                          )}
                        </span>

                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-foreground">
                            {result.label}
                          </span>
                          <span className="block truncate text-xs text-subtle">
                            {result.hint}
                          </span>
                        </span>

                        {result.badge ? (
                          <Badge tone={result.badge.tone} size="sm">
                            {result.badge.text}
                          </Badge>
                        ) : null}

                        {index === active ? (
                          <CornerDownLeft className="size-3.5 shrink-0 text-subtle" />
                        ) : null}
                      </button>
                    </div>
                  )
                })
              )}
            </div>
          </motion.div>
        </>
      ) : null}
    </AnimatePresence>
  )
}
