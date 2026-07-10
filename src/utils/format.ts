/**
 * 格式化工具函数
 */

/**
 * 金额格式化：保留两位小数，添加千分位分隔符
 * @param value 数值
 * @returns 格式化字符串（如 "1,234,567.89"）
 */
export function formatAmount(value: number): string {
  return Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
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
  return `${formatAmount(Number(value || 0) / 10000)} 万元`
}

export function formatYuan(value: number): string {
  return `${formatAmount(Number(value || 0))} 元`
}

export function moneyParts(value: number) {
  const amount = Number(value || 0)
  return {
    yuan: formatYuan(amount),
    wan: formatWan(amount),
    upper: amountToChineseUpper(amount),
  }
}

const chineseDigits = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
const sectionUnits = ['', '万', '亿', '兆']
const digitUnits = ['', '拾', '佰', '仟']

function integerSectionToChinese(section: number) {
  let result = ''
  let zeroPending = false
  for (let unitIndex = 3; unitIndex >= 0; unitIndex -= 1) {
    const divisor = 10 ** unitIndex
    const digit = Math.floor(section / divisor) % 10
    if (digit === 0) {
      if (result) zeroPending = true
    } else {
      if (zeroPending) {
        result += chineseDigits[0]
        zeroPending = false
      }
      result += chineseDigits[digit] + digitUnits[unitIndex]
    }
  }
  return result
}

function integerToChinese(value: number) {
  if (value === 0) return chineseDigits[0]
  let integer = Math.floor(value)
  const sections: number[] = []
  while (integer > 0) {
    sections.unshift(integer % 10000)
    integer = Math.floor(integer / 10000)
  }
  let result = ''
  let zeroPending = false
  sections.forEach((section, index) => {
    const unitIndex = sections.length - index - 1
    if (section === 0) {
      zeroPending = result.length > 0
      return
    }
    if (zeroPending || (result.length > 0 && section < 1000)) {
      result += chineseDigits[0]
    }
    result += integerSectionToChinese(section) + sectionUnits[unitIndex]
    zeroPending = false
  })
  return result.replace(/零+/g, '零').replace(/零(万|亿|兆)/g, '$1').replace(/亿万/g, '亿').replace(/零$/g, '')
}

export function amountToChineseUpper(value: number): string {
  const amount = Math.round(Math.abs(Number(value || 0)) * 100)
  const integer = Math.floor(amount / 100)
  const jiao = Math.floor((amount % 100) / 10)
  const fen = amount % 10
  const sign = Number(value || 0) < 0 ? '负' : ''
  let text = `${sign}人民币${integerToChinese(integer)}元`
  if (jiao === 0 && fen === 0) return `${text}整`
  if (jiao > 0) text += `${chineseDigits[jiao]}角`
  if (fen > 0) text += `${jiao === 0 ? '零' : ''}${chineseDigits[fen]}分`
  return text
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
