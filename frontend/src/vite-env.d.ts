/// <reference types="vite/client" />

/**
 * Build-time environment variables.
 *
 * Everything declared here is compiled into the browser bundle and is publicly
 * readable — no secret may ever be added to this interface. Runtime
 * configuration for containers is injected separately via `/config.js`; see
 * `src/constants/config.ts`.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_WS_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
