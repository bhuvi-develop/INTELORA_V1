import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * INTELORA — Presentation Layer build configuration.
 *
 * Manual chunking keeps the initial payload small. ECharts and Framer Motion
 * are the two heaviest dependencies and neither is needed to paint the splash
 * screen, so isolating them lets the brand sequence start immediately while
 * the rest streams in behind it.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    port: 5173,
    strictPort: false,
    host: true,
  },

  preview: {
    port: 4173,
    host: true,
  },

  build: {
    target: 'es2022',
    sourcemap: false,
    chunkSizeWarningLimit: 900,

    /**
     * Build output goes to `static/`, not Vite's default `assets/`.
     *
     * `/assets` is an application route — the Asset Registry — and the default
     * would shadow it: nginx serves `/assets/` as a static directory, so
     * `/assets` and `/assets/:id` return 404 on direct load or refresh. A
     * build-tool default should never dictate the URL space of the product.
     */
    assetsDir: 'static',
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['echarts'],
          motion: ['framer-motion'],
          query: ['@tanstack/react-query'],
        },
      },
    },
  },
})
