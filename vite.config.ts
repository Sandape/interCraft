/// <reference types="vitest" />
import { defineConfig, normalizePath } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const watchRoot = normalizePath(__dirname)
const useShallowDevWatch = process.env.VITE_SHALLOW_WATCH === '1'
const watchTopLevelDirs = new Set(['public', 'src'])
const watchRootFiles = new Set([
  '.env',
  '.env.development',
  '.env.development.local',
  '.env.local',
  'index.html',
  'package-lock.json',
  'package.json',
  'postcss.config.js',
  'tailwind.config.js',
  'tsconfig.json',
  'vite.config.ts',
])

function shouldIgnoreDevWatch(rawPath: string): boolean {
  const candidate = normalizePath(rawPath).replace(/\/$/, '')
  if (candidate === watchRoot) {
    return false
  }
  if (!candidate.startsWith(`${watchRoot}/`)) {
    return false
  }

  const relative = candidate.slice(watchRoot.length + 1)
  const [topLevel] = relative.split('/')
  if (watchTopLevelDirs.has(topLevel)) {
    return false
  }

  return !watchRootFiles.has(relative)
}

/**
 * 2026-07-05 admin entry merge into main SPA migration note.
 *
 * REQ-044 admin routing originally used a separate HTML entry + dev-time
 * fallback to index.admin.html via adminConsolePathPlugin. After this
 * migration:
 *   - index.admin.html, src/admin/main.tsx removed
 *   - admin routes mount via src/App.tsx under /admin-console/*
 *   - Single SPA entry (index.html) + React Router serves /admin-console/*
 *
 * Rollback guards: see specs/044-admin-console-redesign/spec.md
 * "Migration 2026-07-05" section.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // REMOVED: CJS stub aliases caused runtime failures (zustand store selector
      // returned null). Instead rely on optimizeDeps.include to pre-bundle these
      // CJS packages with proper ESM interop.
      // 'use-sync-external-store/with-selector.js': ...,
      // 'use-sync-external-store/shim/with-selector.js': ...,
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    hmr: process.env.VITE_DISABLE_HMR === '1' ? false : undefined,
    watch: {
      // Vite watches `root` recursively on startup. In this workspace that root
      // also contains backend virtualenvs, worktrees, logs, specs, and evidence
      // folders; on Windows, initializing those fs.watch handles blocks the dev
      // server long enough to make both the page and proxied APIs look hung.
      // Keep recursive HMR for frontend files, but never recurse into the rest
      // of the workspace. Set VITE_SHALLOW_WATCH=1 for diagnosis if Windows
      // fs.watch gets slow again on a local machine.
      depth: useShallowDevWatch ? 0 : undefined,
      ignored: shouldIgnoreDevWatch,
    },
    // Vite 5.4+: warm up critical modules on server start.
    // DISABLED (2026-07-07): warmup causes progressive degradation on this
    // project — each subsequent request gets slower. Enable only after Vite
    // team fixes the transform-cache interaction.
    // warmup: {
    //   clientFiles: [
    //     './src/main.tsx',
    //     './src/index.css',
    //     './src/stores/useAuthStore.ts',
    //     './src/api/token-storage.ts',
    //     './src/lib/requireAuth.ts',
    //     './src/pages/Login.tsx',
    //   ],
    // },
    // Proxy /api and /openapi.json to the FastAPI backend on 127.0.0.1.
    // Using 127.0.0.1 (IPv4) avoids the Windows "localhost resolves to ::1 first"
    // Happy-Eyeballs pitfall when uvicorn binds IPv4 only. This also removes the
    // need for CORS configuration in the browser.
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
      '/openapi.json': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: () => '/api/v1/openapi.json',
      },
    },
  },
  optimizeDeps: {
    // The app has a large lazy route graph. Letting Vite crawl every static
    // import on cold start blocks the dev server event loop, which also delays
    // proxied API requests. Keep first-screen deps explicit and let route code
    // transform on demand.
    noDiscovery: true,
    holdUntilCrawlEnd: false,
    include: [
      '@tanstack/react-query',
      'clsx',
      'dexie',
      'dexie/dist/dexie',
      'eventemitter3',
      'js-sha256',
      'lucide-react',
      'react',
      'react-dom',
      'react-dom/client',
      'react/jsx-runtime',
      'react-router-dom',
      'recharts',
      'zustand',
      'use-sync-external-store/with-selector',
      'use-sync-external-store/shim/with-selector',
    ],
  },
  build: {
    rollupOptions: {
      // Admin console now mounts inside the main SPA at /admin-console/*.
      // Old standalone `index.admin.html` entry was removed 2026-07-05 —
      // see specs/044-*/spec.md Migration block.
      input: {
        main: path.resolve(__dirname, 'index.html'),
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}', 'tests/unit/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'tests/e2e/**'],
  },
})
