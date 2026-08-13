const MIN_SCALE = 0.5
const MAX_SCALE = 2.5

export function clampPage(page: number, totalPages: number): number {
  const safeTotal = Number.isFinite(totalPages) ? Math.max(1, Math.trunc(totalPages)) : 1
  const safePage = Number.isFinite(page) ? Math.trunc(page) : 1
  return Math.min(safeTotal, Math.max(1, safePage))
}

export function clampScale(scale: number): number {
  const safeScale = Number.isFinite(scale) ? scale : 1
  return Math.round(Math.min(MAX_SCALE, Math.max(MIN_SCALE, safeScale)) * 100) / 100
}

export function neighborPages(page: number, totalPages: number): number[] {
  if (!Number.isFinite(totalPages) || totalPages < 1) return []
  const safeTotal = Math.trunc(totalPages)
  const current = clampPage(page, safeTotal)
  return [current - 1, current, current + 1].filter(
    (candidate) => candidate >= 1 && candidate <= safeTotal,
  )
}

export interface RenderTokenGuard {
  next(): number
  invalidate(): number
  isCurrent(token: number): boolean
}

export function createRenderTokenGuard(): RenderTokenGuard {
  let current = 0
  return {
    next() {
      current += 1
      return current
    },
    invalidate() {
      current += 1
      return current
    },
    isCurrent(token) {
      return token === current
    },
  }
}
