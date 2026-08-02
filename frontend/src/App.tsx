import { RouterProvider } from 'react-router-dom'

import { AppProviders } from '@/context/AppProviders'
import { router } from '@/routes'

/**
 * INTELORA — Presentation Layer root.
 *
 * Providers wrap the router rather than the reverse, so that theme, live
 * stream and boot state all survive navigation. The splash sequence is owned
 * by the shell inside the router, and because the provider tree mounts once
 * per page load it plays on launch and refresh but never on in-app navigation.
 */
export function App() {
  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
}

export default App
