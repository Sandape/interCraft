/**
 * REQ-053 — ResearchReportPage unit coverage (T069 + T071).
 *
 * Asserts:
 *  - T069: when a report is loaded, the page surfaces 6 chapter cards plus
 *    a 📊 历史对比 table.
 *  - T071: the comparison table renders the parsed 维度 / 上次 / 本次 / 趋势
 *    rows from the markdown; missing sections show the "暂无历史对比数据"
 *    fallback.
 *  - SC-009: clicking a star submits a rating via the PATCH hook.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createElement, type ReactNode } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ResearchReportPage from '@/pages/ResearchReportPage'

const mockGetResearchReport = vi.fn()
const mockListResearchReports = vi.fn()
const mockRateResearchReport = vi.fn()

vi.mock('@/api/research', () => ({
  getResearchReport: (...args: unknown[]) => mockGetResearchReport(...args),
  listResearchReports: (...args: unknown[]) => mockListResearchReports(...args),
  rateResearchReport: (...args: unknown[]) => mockRateResearchReport(...args),
}))

function wrap(ui: ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/research-reports/job-1/report-1']}>
        <Routes>
          <Route path="/research-reports/:jobId/:reportId" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const FULL_MARKDOWN = `# 📋 面试概览
公司：阿里巴巴 · 岗位：Java 高级开发

# 🏢 公司与产品速览
- 阿里云
- 钉钉

# 📝 面经汇总
1. JVM 调优
2. 多线程
3. Spring 原理

# 🎯 高频考察点
- JVM
- 并发

# ⚠️ 你的薄弱环节
tech_depth 与 algorithm

# 💡 最后建议
多刷题

# 📊 历史对比
| 维度 | 上次 | 本次 | 趋势 |
| --- | --- | --- | --- |
| tech_depth | 3.5 | 4.2 | ↑ |
| algorithm | 4.0 | 3.8 | ↓ |
`

const REPORT = {
  id: 'report-1',
  report_type: 'pre_interview_research' as const,
  job_id: 'job-1',
  interview_time: '2026-07-10T14:00:00+08:00',
  summary_md: FULL_MARKDOWN,
  research_task_id: 'task-1',
  rating: 3,
  generated_at: '2026-07-10T09:05:00+08:00',
  delivery_status: 'sent' as const,
  delivered_at: '2026-07-10T09:05:30+08:00',
  quality_check_passed: true,
}

const NO_COMPARISON_REPORT = {
  ...REPORT,
  id: 'report-2',
  summary_md: `# 📋 面试概览
公司简介

# 🏢 公司与产品速览
核心业务

# 📝 面经汇总
1. 题1
2. 题2
3. 题3

# 🎯 高频考察点
- Java

# ⚠️ 你的薄弱环节
tech_depth

# 💡 最后建议
多练
`,
}

describe('ResearchReportPage — REQ-053 (T069 + T071)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListResearchReports.mockResolvedValue({ data: [REPORT] })
  })

  it('T069 — renders 6 chapter cards + history comparison', async () => {
    mockGetResearchReport.mockResolvedValue(REPORT)
    wrap(<ResearchReportPage />)
    await screen.findByTestId('research-report-header')

    // The 6 SPEC chapters are always visible.
    for (const slug of ['overview', 'company', 'experience', 'topics', 'weakness', 'tips']) {
      expect(
        await screen.findByTestId(`research-report-section-${slug}`),
        `chapter card "${slug}" must be visible`,
      ).toBeInTheDocument()
    }

    // Comparison table present.
    const table = await screen.findByTestId('research-report-comparison-table')
    expect(table).toBeInTheDocument()
    // The parsed rows surface the trend icons in the right column.
    expect(table).toHaveTextContent('tech_depth')
    expect(table).toHaveTextContent('algorithm')
    expect(table).toHaveTextContent('进步')
    expect(table).toHaveTextContent('退步')
  })

  it('T071 — falls back to "暂无历史对比数据" when the section is absent', async () => {
    mockGetResearchReport.mockResolvedValue(NO_COMPARISON_REPORT)
    wrap(<ResearchReportPage />)
    await screen.findByTestId('research-report-header')
    expect(await screen.findByTestId('research-report-comparison-empty')).toHaveTextContent(
      '暂无历史对比数据',
    )
  })

  it('SC-009 — clicking a star submits a rating via PATCH', async () => {
    mockGetResearchReport.mockResolvedValue(REPORT)
    mockRateResearchReport.mockResolvedValue({ ...REPORT, rating: 4 })
    wrap(<ResearchReportPage />)
    await screen.findByTestId('research-report-rating-stars')
    fireEvent.click(screen.getByTestId('research-report-star-4'))
    await waitFor(() =>
      expect(mockRateResearchReport).toHaveBeenCalledWith('report-1', 4),
    )
  })
})
