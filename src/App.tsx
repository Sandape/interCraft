import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { AppShell } from '@/components/layout/AppShell'
import Dashboard from '@/pages/Dashboard'
import ResumeList from '@/pages/ResumeList'
import ResumeEditor from '@/pages/ResumeEditor'
import InterviewList from '@/pages/InterviewList'
import InterviewLive from '@/pages/InterviewLive'
import InterviewReport from '@/pages/InterviewReport'
import Profile from '@/pages/Profile'
import Settings from '@/pages/Settings'
import Jobs from '@/pages/Jobs'
import Resources from '@/pages/Resources'
import Help from '@/pages/Help'
import Login from '@/pages/Login'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* Auth 路由 - 无侧边栏 */}
          <Route path="/login" element={<Login />} />

          {/* 主应用路由 - 共享 AppShell */}
          <Route
            path="/*"
            element={
              <AppShell>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<Dashboard />} />

                  {/* 简历中心 */}
                  <Route path="/resume" element={<ResumeList />} />
                  <Route path="/resume/:branchId" element={<ResumeEditor />} />

                  {/* 模拟面试 */}
                  <Route path="/interview" element={<InterviewList />} />
                  <Route path="/interview/new" element={<InterviewLive />} />
                  <Route path="/interview/report/:id" element={<InterviewReport />} />

                  {/* 个人画像 */}
                  <Route path="/profile" element={<Profile />} />

                  {/* 求职追踪 */}
                  <Route path="/jobs" element={<Jobs />} />

                  {/* 学习资源 */}
                  <Route path="/resources" element={<Resources />} />

                  {/* 设置 */}
                  <Route path="/settings" element={<Settings />} />

                  {/* 帮助 */}
                  <Route path="/help" element={<Help />} />

                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </AppShell>
            }
          />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
