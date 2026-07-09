/**
 * [REQ-048 US4 / T092] cardMarkdown.ts — Markdown generator for the doubao
 * card copy CTA (FR-054, US4.AS4, AC-24).
 *
 * Mirrors the canonical Python implementation at
 * `backend/app/services/card_renderer/markdown.py` so the test surface
 * is identical (Python is canonical for the contract; this file is
 * the frontend runtime).
 *
 * The output format is locked per AC-24:
 *   # 面试大纲
 *   ## 公司: <target_company>
 *   ## 岗位: <target_position>
 *   ## 难度: <difficulty>
 *   ## 时长: <minutes> 分钟
 *   ## 关注重点: 1. <area>  2. <area> …
 *   ## 面试提示: 1. <tip>  2. <tip> …
 *   ## 大纲: 1. <question>  2. <question> …
 *
 * The Markdown is **never truncated** — the full plan flows through
 * so the user can copy + paste the complete outline into Doubao /
 * Notion / WeChat.
 */

export interface InterviewFocusArea {
  area?: string | null
  name?: string | null
  weight?: number | null
  reason?: string | null
}

export interface InterviewPlanForMarkdown {
  target_company?: string | null
  company?: string | null
  target_position?: string | null
  position?: string | null
  interview_difficulty?: string | null
  estimated_duration_minutes?: number | string | null
  focus_areas?: InterviewFocusArea[] | null
  suggested_questions?: string[] | null
  tips?: string[] | null
}

function asList<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : []
}

function safeStr(value: unknown, fallback: string = ''): string {
  if (value === null || value === undefined) return fallback
  return String(value)
}

function focusAreaText(area: InterviewFocusArea): string {
  const name = safeStr(area.area ?? area.name)
  const reason = safeStr(area.reason)
  if (reason) return name ? `${name}（${reason}）` : reason
  return name
}

export function buildCardMarkdown(plan: InterviewPlanForMarkdown | null | undefined): string {
  const company = safeStr(plan?.target_company ?? plan?.company)
  const position = safeStr(plan?.target_position ?? plan?.position)
  const difficulty = safeStr(plan?.interview_difficulty)
  const duration = safeStr(plan?.estimated_duration_minutes)

  const focusAreas = asList(plan?.focus_areas)
    .map(focusAreaText)
    .filter((s) => s)
  const questions = asList(plan?.suggested_questions)
    .map((q) => safeStr(q))
    .filter((s) => s)
  const tips = asList(plan?.tips).map((t) => safeStr(t)).filter((s) => s)

  const lines: string[] = ['# 面试大纲']
  lines.push(`## 公司: ${company}`)
  lines.push(`## 岗位: ${position}`)
  if (difficulty) lines.push(`## 难度: ${difficulty}`)
  if (duration) lines.push(`## 时长: ${duration} 分钟`)

  if (focusAreas.length > 0) {
    lines.push('## 关注重点:')
    focusAreas.slice(0, 8).forEach((area, i) => {
      lines.push(`${i + 1}. ${area}`)
    })
  }

  if (tips.length > 0) {
    lines.push('## 面试提示:')
    tips.slice(0, 8).forEach((tip, i) => {
      lines.push(`${i + 1}. ${tip}`)
    })
  }

  if (questions.length > 0) {
    lines.push('## 大纲:')
    questions.slice(0, 8).forEach((q, i) => {
      lines.push(`${i + 1}. ${q}`)
    })
  } else {
    lines.push('## 大纲: (无)')
  }

  lines.push('')
  lines.push('— 来自 InterCraft 豆包面试卡')

  return lines.join('\n')
}

export default buildCardMarkdown