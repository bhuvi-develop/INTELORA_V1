import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './styles/index.css'

/**
 * Application bootstrap.
 *
 * The theme class is already on `<html>` by this point — an inline script in
 * `index.html` applies it before first paint, so the interface never renders
 * in the wrong theme and flashes.
 */

const container = document.getElementById('root')

if (!container) {
  throw new Error('INTELORA could not start: no #root element in the document.')
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
