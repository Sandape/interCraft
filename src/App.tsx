/**
 * App.tsx — providers + router + auth guard.
 */
import React, { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { AppShell } from '@/components/layout/AppShell'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { hasTokens } from '@/api/token-storage'
import { requireAuth } from '@/lib/requireAuth'

/* ── Eager (first-screen, keep as static import) ── */
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import SharedAbilityProfile from '@/pages/SharedAbilityProfile'

/* ── Lazy (code-split on route) ── */
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const ResumeList = lazy(() => import('@/pages/ResumeList'))
const ResumeListV2 = lazy(() => import('@/pages/ResumeListV2'))
const ResumeEditorV2 = lazy(() => import('@/pages/ResumeEditorV2'))
const PublicResumeV2 = lazy(() => import('@/pages/PublicResumeV2'))
const Square = lazy(() => import('@/modules/resume/marketplace/Square'))
const Jobs = lazy(() => import('@/pages/Jobs'))
const ErrorBook = lazy(() => import('@/pages/ErrorBook'))
const InterviewList = lazy(() => import('@/pages/InterviewList'))
const InterviewModeSelect = lazy(() => import('@/pages/InterviewModeSelect'))
const InterviewLive = lazy(() => import('@/pages/InterviewLive'))
const InterviewReport = lazy(() => import('@/pages/InterviewReport'))
const Settings = lazy(() => import('@/pages/Settings'))
const AgentSettings = lazy(() => import('@/pages/AgentSettings'))
const GeneralCoach = lazy(() => import('@/pages/GeneralCoach'))
const Help = lazy(() => import('@/pages/Help'))
const AbilityProfile = lazy(() => import('@/pages/AbilityProfile'))
const AbilityProfileDetail = lazy(() => import('@/pages/AbilityProfileDetail'))
const PMDashboard = lazy(() => import('@/pages/PMDashboard'))
// REQ-053 (T069) — full report viewer.
const ResearchReportPage = lazy(() => import('@/pages/ResearchReportPage'))
// REQ-055 — derive run progress.
const DeriveProgress = lazy(() =>
  import('@/modules/resume/derive/DeriveProgress').then((m) => ({ default: m.DeriveProgress })),
)

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// 020 (FIX-009, D-016) — Use the pure `requireAuth` decision. Renders
// a neutral loading state while `status === 'unknown'` so the protected
// page never mounts until the user is confirmed.
function AuthGuard({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const location = useLocation()

  const decision = requireAuth({ hasTokens: hasTokens(), status })
  if (decision.kind === 'redirect') {
    return <Navigate to={decision.to} replace state={{ from: location }} />
  }
  if (decision.kind === 'loading') {
    return (
      <div
        data-testid="auth-loading"
        className="flex items-center justify-center min-h-screen text-sm text-ink-3"
      >
        正在校验登录状态…
      </div>
    )
  }
  return <>{children}</>
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status)
  if (status === 'authenticated') return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

export function AppRoutes() {
  // Eagerly resolve current user on mount.
  useCurrentUser()
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicOnly>
            <Login />
          </PublicOnly>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnly>
            <Register />
          </PublicOnly>
        }
      />
      <Route path="/shared/:shareToken" element={<SharedAbilityProfile />} />
      <Route path="/r/:username/:slug" element={<PublicResumeV2 />} />
      <Route
        path="/*"
        element={
          <AuthGuard>
            <AppShell>
              <Suspense fallback={<div className="flex items-center justify-center min-h-screen text-sm text-ink-3">正在加载页面…</div>}>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/resume" element={<ResumeList />} />
                <Route path="/resume/derive/:runId" element={<DeriveProgress />} />
                <Route path="/resume/marketplace" element={<Square />} />
                {/* Canonical editor is V2; keep /resume/v2/:id as a stable alias. */}
                <Route path="/resume/v2/:id" element={<ResumeEditorV2 />} />
                <Route path="/resume-v2" element={<ResumeListV2 />} />
                <Route path="/resume-v2/new" element={<ResumeListV2 />} />
                <Route path="/resume/:id" element={<ResumeEditorV2 />} />
                <Route path="/interview" element={<InterviewList />} />
                <Route path="/interview/mode" element={<InterviewModeSelect />} />
                <Route path="/interview/new" element={<InterviewLive />} />
                <Route path="/interview/:id/live" element={<InterviewLive />} />
                <Route path="/interview/:id/report" element={<InterviewReport />} />
                {/* Legacy Jobs CTA / deep links without /live suffix */}
                <Route path="/interview/:id" element={<InterviewLive />} />
                <Route path="/profile" element={<Navigate to="/ability-profile" replace />} />
                <Route path="/ability-profile" element={<AbilityProfile />} />
                <Route path="/ability-profile/:abilityKey" element={<AbilityProfileDetail />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route
                  path="/research-reports/:jobId/:reportId"
                  element={<ResearchReportPage />}
                />
                <Route path="/error-book" element={<ErrorBook />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/agent" element={<AgentSettings />} />
                <Route path="/coach" element={<GeneralCoach />} />
                <Route path="/help" element={<Help />} />
                <Route path="/pm-dashboard" element={<PMDashboard />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
              </Suspense>
            </AppShell>
          </AuthGuard>
        }
      />
    </Routes>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter
          future={{
            v7_startTransition: true,
            v7_relativeSplatPath: true,
          }}
        >
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
