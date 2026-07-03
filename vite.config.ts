/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      // REQ-039 B2: admin console ships as a second entry alongside the
      // main app. Each HTML page (index.html, index.admin.html) builds
      // its own chunk set so the admin bundle never bloats the user
      // app and vice versa.
      input: {
        main: path.resolve(__dirname, 'index.html'),
        admin: path.resolve(__dirname, 'index.admin.html'),
      },
    },
  },
  server: {
    port: 5173,
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
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}', 'tests/unit/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'tests/e2e/**'],
  },
})
