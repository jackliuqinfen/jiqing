/**
 * 日期工具函数
 */

/**
 * 判断是否超期（截止日期已过且今天大于截止日）
 * @param deadline ISO 8601 日期字符串
 * @returns 是否超期
 */
export function isOverdue(deadline: string): boolean {
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  const dl = new Date(deadline)
  dl.setHours(0, 0, 0, 0)
  return dl < now
}

/**
 * 格式化日期为 yyyy-MM-dd
 */
export function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/**
 * 获取今天的 ISO 日期字符串
 */
export function todayISO(): string {
  return new Date().toISOString().split('T')[0]
}

/**
 * 获取 N 天后的 ISO 日期
 */
export function daysFromNow(n: number): string {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return d.toISOString().split('T')[0]
}

/**
 * 计算剩余天数（负数表示已超期）
 */
export function remainingDays(deadline: string): number {
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  const dl = new Date(deadline)
  dl.setHours(0, 0, 0, 0)
  return Math.ceil((dl.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}
