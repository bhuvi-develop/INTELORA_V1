import { Compass, Home } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageTransition } from '@/components/layout'
import { Button, Card } from '@/components/ui'
import { ROUTES } from '@/constants/navigation'

/**
 * Not found.
 *
 * Also the landing point for planned modules if one is reached by URL, so the
 * copy avoids implying the address was a mistake — it may simply not exist
 * yet.
 */
export function NotFoundPage() {
  return (
    <PageTransition>
      <div className="grid min-h-[60vh] place-items-center">
        <Card
          elevation="secondary"
          className="flex max-w-md flex-col items-center gap-5 p-10 text-center"
        >
          <span className="grid size-14 place-items-center rounded-full border border-border bg-surface-sunken text-primary">
            <Compass className="size-6" />
          </span>

          <div className="space-y-2">
            <h1 className="font-display text-xl font-bold text-foreground">
              This module is not available
            </h1>
            <p className="text-sm leading-relaxed text-muted">
              The address you followed does not correspond to a module in this release.
              It may be planned for a future phase.
            </p>
          </div>

          <Button variant="primary" size="sm" asChild>
            <Link to={ROUTES.cockpit}>
              <Home className="size-4" />
              Return to Enterprise Cockpit
            </Link>
          </Button>
        </Card>
      </div>
    </PageTransition>
  )
}

export default NotFoundPage
