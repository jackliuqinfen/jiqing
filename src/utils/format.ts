/**
 * 格式化工具函数
 */

/**
 * 金额格式化：保留两位小数，添加千分位分隔符
 * @param value 数值
 * @returns 格式化字符串（如 "1,234,567.89"）
 */
export function formatAmount(value: number): string {
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/**
 * 金额格式化（带人民币符号）
 */
export function formatCNY(value: number): string {
  return `¥${formatAmount(value)}`
}

/**
 * 金额格式化（万元）
 */
export function formatWan(value: number): string {
  return `${(value / 10000).toFixed(2)} 万元`
}

/**
 * 提取姓名的首字母作为头像占位
 * @param name 姓名
 * @returns 1-2 个大写字母
 */
export function getInitials(name: string): string {
  if (!name) return '?'
  // 取最后两个字的首字母（中文名）或拼音首字母
  const chars = name.trim()
  if (chars.length <= 2) return chars
  // 中文：取后两个字的拼音首字母近似
  return chars.slice(-2)
}

/**
 * 生成唯一 UUID v4
 */
export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
