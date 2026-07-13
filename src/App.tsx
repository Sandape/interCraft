/**
 * App.tsx — providers + router + auth guard.
 */
import React, { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom'
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
import PublicHome from '@/pages/PublicHome'

/* ── Lazy (code-split on route) ── */
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const DemoWorkspace = lazy(() => import('@/pages/DemoWorkspace'))
const Onboarding = lazy(() => import('@/pages/Onboarding'))
const ResumeList = lazy(() => import('@/pages/ResumeList'))
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
const AITaskCenter = lazy(() => import('@/pages/AITaskCenter'))
const AITaskDetail = lazy(() => import('@/pages/AITaskDetail'))
const AIPoints = lazy(() => import('@/pages/AIPoints'))
const Help = lazy(() => import('@/pages/Help'))
const AbilityProfile = lazy(() => import('@/pages/AbilityProfile'))
const AbilityProfileDetail = lazy(() => import('@/pages/AbilityProfileDetail'))
const PMDashboard = lazy(() => import('@/pages/PMDashboard'))
const NotFound = lazy(() => import('@/pages/NotFound'))
const AdminAppRoutes = lazy(() =>
  import('@/admin/routes').then((module) => ({ default: module.AdminAppRoutes })),
)
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

function PublicOnly({
  children,
  authenticatedTo = '/dashboard',
}: {
  children: React.ReactNode
  authenticatedTo?: string
}) {
  const status = useAuthStore((s) => s.status)
  if (status === 'authenticated') return <Navigate to={authenticatedTo} replace />
  return <>{children}</>
}

function LegacyResumeEditorRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={id ? `/resume/${id}` : '/resume'} replace />
}

export function InterviewNewEntry() {
  const location = useLocation()
  return <Navigate to={`/interview/mode${location.search}`} replace />
}

export function AppRoutes() {
  // Eagerly resolve current user on mount.
  useCurrentUser()
  return (
    <Routes>
      <Route
        path="/"
        element={
          <PublicOnly>
            <PublicHome />
          </PublicOnly>
        }
      />
      <Route
        path="/demo"
        element={
          <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-ink-3">正在加载示例工作台…</div>}>
            <DemoWorkspace />
          </Suspense>
        }
      />
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
          <PublicOnly authenticatedTo="/onboarding">
            <Register />
          </PublicOnly>
        }
      />
      <Route path="/shared/:shareToken" element={<SharedAbilityProfile />} />
      <Route path="/r/:username/:slug" element={<PublicResumeV2 />} />
      <Route
        path="/onboarding"
        element={
          <AuthGuard>
            <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-ink-3">正在恢复引导进度…</div>}>
              <Onboarding />
            </Suspense>
          </AuthGuard>
        }
      />
      <Route
        path="/admin-console/*"
        element={
          <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-ink-3">正在加载管理后台…</div>}>
            <AdminAppRoutes />
          </Suspense>
        }
      />
      <Route
        path="/*"
        element={
          <AuthGuard>
            <AppShell>
              <Suspense fallback={<div className="flex items-center justify-center min-h-screen text-sm text-ink-3">正在加载页面…</div>}>
              <Routes>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/resume" element={<ResumeList />} />
                <Route path="/resume/derive/:runId" element={<DeriveProgress />} />
                <Route path="/resume/marketplace" element={<Square />} />
                {/* Legacy aliases keep old bookmarks working while converging on canonical routes. */}
                <Route path="/resume/v2/:id" element={<LegacyResumeEditorRedirect />} />
                <Route path="/resume-v2" element={<Navigate to="/resume" replace />} />
                <Route path="/resume-v2/new" element={<Navigate to="/resume?new=true" replace />} />
                <Route path="/resume/:id" element={<ResumeEditorV2 />} />
                <Route path="/interview" element={<InterviewList />} />
                <Route path="/interview/mode" element={<InterviewModeSelect />} />
                <Route path="/interview/new" element={<InterviewNewEntry />} />
                <Route path="/interview/:id/live" element={<InterviewLive />} />
                <Route path="/interview/:id/report" element={<InterviewReport />} />
                {/* Legacy Jobs CTA / deep links without /live suffix */}
                <Route path="/interview/:id" element={<InterviewLive />} />
                <Route path="/profile" element={<Navigate to="/ability-profile" replace />} />
                <Route path="/ability-profile" element={<AbilityProfile />} />
                <Route path="/ability-profile/:abilityKey" element={<AbilityProfileDetail />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="/jobs/:jobId" element={<Jobs />} />
                <Route
                  path="/research-reports/:jobId/:reportId"
                  element={<ResearchReportPage />}
                />
                <Route path="/error-book" element={<ErrorBook />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/agent" element={<AgentSettings />} />
                <Route path="/coach" element={<GeneralCoach />} />
                <Route path="/ai-tasks" element={<AITaskCenter />} />
                <Route path="/ai-tasks/:taskId" element={<AITaskDetail />} />
                <Route path="/ai-points" element={<AIPoints />} />
                <Route path="/help" element={<Help />} />
                <Route path="/pm-dashboard" element={<PMDashboard />} />
                <Route path="*" element={<NotFound />} />
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
