/**
 * App.tsx — providers + router + auth guard.
 */
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { AppShell } from '@/components/layout/AppShell'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { hasTokens } from '@/api/token-storage'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import Dashboard from '@/pages/Dashboard'
import ResumeList from '@/pages/ResumeList'
import ResumeEditor from '@/pages/ResumeEditor'
import Profile from '@/pages/Profile'
import Jobs from '@/pages/Jobs'
import ErrorBook from '@/pages/ErrorBook'
import InterviewList from '@/pages/InterviewList'
import InterviewLive from '@/pages/InterviewLive'
import InterviewReport from '@/pages/InterviewReport'
import Settings from '@/pages/Settings'
import GeneralCoach from '@/pages/GeneralCoach'
import Help from '@/pages/Help'
import AbilityProfile from '@/pages/AbilityProfile'
import AbilityProfileDetail from '@/pages/AbilityProfileDetail'
import SharedAbilityProfile from '@/pages/SharedAbilityProfile'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function AuthGuard({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const location = useLocation()

  if (!hasTokens() && status === 'unknown') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return <>{children}</>
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status)
  if (status === 'authenticated') return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

function AppRoutes() {
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
      <Route
        path="/*"
        element={
          <AuthGuard>
            <AppShell>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/resume" element={<ResumeList />} />
                <Route path="/resume/:branchId" element={<ResumeEditor />} />
                <Route path="/interview" element={<InterviewList />} />
                <Route path="/interview/new" element={<InterviewLive />} />
                <Route path="/interview/:id/live" element={<InterviewLive />} />
                <Route path="/interview/:id/report" element={<InterviewReport />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/ability-profile" element={<AbilityProfile />} />
                <Route path="/ability-profile/:abilityKey" element={<AbilityProfileDetail />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="/error-book" element={<ErrorBook />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/coach" element={<GeneralCoach />} />
                <Route path="/help" element={<Help />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
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
