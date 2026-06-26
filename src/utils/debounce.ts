/**
 * 防抖函数：延迟执行，只保留最后一次调用
 * @param fn 目标函数
 * @param delay 延迟时间（ms）
 */
export function debounce<T extends (...args: any[]) => void>(
  fn: T,
  delay: number = 300
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn(...args)
      timer = null
    }, delay)
  }
}

/**
 * 节流函数：固定间隔内最多执行一次
 * @param fn 目标函数
 * @param interval 间隔时间（ms）
 */
export function throttle<T extends (...args: any[]) => void>(
  fn: T,
  interval: number = 200
): (...args: Parameters<T>) => void {
  let lastTime = 0
  return (...args: Parameters<T>) => {
    const now = Date.now()
    if (now - lastTime >= interval) {
      lastTime = now
      fn(...args)
    }
  }
}

/**
 * 请求防重复锁（乐观更新用）
 * @returns { lock, unlock, isLocked }
 */
export function createRequestLock() {
  let locked = false
  return {
    lock: () => { locked = true },
    unlock: () => { locked = false },
    isLocked: () => locked,
  }
}
