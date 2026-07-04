/**
 * Admin Console entry point — REQ-039 B2.
 *
 * Mounts the admin router inside `#admin-root` (index.admin.html).
 *
 * Auth flow:
 * - Eagerly call `useCurrentUser()` so the AuthGuard has its decision
 *   ready before the first render.
 * - User without admin role: kicked to /login.
 */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminAppRoutes } from './routes'
import './styles/admin.css'
import './styles/ai-operations.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const rootEl = document.getElementById('admin-root')
if (!rootEl) throw new Error('admin-root element missing from index.admin.html')

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <AdminAppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
