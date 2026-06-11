import { type ClassValue, clsx } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

/**
 * 格式化数字：1234 -> 1,234
 */
export function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

/**
 * 相对时间：3分钟前 / 2小时前 / 昨天 / 3天前
 */
export function timeAgo(date: Date | string | number): string {
  const d = typeof date === 'object' ? date : new Date(date)
  const now = Date.now()
  const diff = now - d.getTime()
  const sec = Math.floor(diff / 1000)
  const min = Math.floor(sec / 60)
  const hr = Math.floor(min / 60)
  const day = Math.floor(hr / 24)

  if (sec < 60) return '刚刚'
  if (min < 60) return `${min}分钟前`
  if (hr < 24) return `${hr}小时前`
  if (day === 1) return '昨天'
  if (day < 7) return `${day}天前`
  if (day < 30) return `${Math.floor(day / 7)}周前`
  if (day < 365) return `${Math.floor(day / 30)}个月前`
  return `${Math.floor(day / 365)}年前`
}

/**
 * 格式化持续时间：125 -> 02:05
 */
export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
}

/**
 * 截断文本
 */
export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}
