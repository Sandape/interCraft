// This file exists to handle vite CJS→ESM interop at build time.
// At dev time, optimizeDeps.include pre-bundles the real CJS packages.
// This stub is only used when the alias is active - which it is not.
// If you see this loaded at runtime, remove it from vite.config.ts aliases
// and rely on optimizeDeps.include instead.

import __real from '../node_modules/use-sync-external-store/shim/with-selector.js'
export const useSyncExternalStoreWithSelector = __real.useSyncExternalStoreWithSelector || (() => null)
export default __real.useSyncExternalStoreWithSelector ? { useSyncExternalStoreWithSelector } : { useSyncExternalStoreWithSelector: () => null }