const TECHNICAL_PATTERNS = [
  /sqlite/i,
  /database/i,
  /sql/i,
  /traceback/i,
  /not found/i,
  /failed to fetch/i,
  /network/i,
  /请求失败:\s*\d+/i,
  /internal server error/i,
]

export function friendlyErrorMessage(error: unknown, fallback = '数据加载失败，请稍后重试或联系管理员') {
  const raw = error instanceof Error ? error.message : String(error || '')
  const message = raw.trim()
  if (!message) return fallback
  if (message.includes('没有权限') || message.includes('权限')) return '当前账号没有权限执行该操作，请联系管理员处理。'
  if (message.includes('请先登录') || message.includes('UNAUTHORIZED')) return '登录状态已过期，请重新登录后继续操作。'
  if (message.includes('文件超过上传大小限制')) return '文件超过上传大小限制，请压缩后重新上传。'
  if (message.includes('不允许上传') || message.includes('不支持上传')) return message
  if (message.includes('暂不支持在线预览')) return '该文件暂不支持在线预览，请下载后查看。'
  if (TECHNICAL_PATTERNS.some((pattern) => pattern.test(message))) return fallback
  return message
}
