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

export interface DisposableRenderTask {
  cancel(): void
  promise: Promise<unknown>
}

export interface DisposablePdfDocument {
  cleanup(): Promise<unknown>
}

export interface DisposablePdfLoadingTask {
  destroy(): Promise<unknown>
}

export interface PdfPreviewResources {
  renderTask: DisposableRenderTask | null
  pdfDocument: DisposablePdfDocument | null
  loadingTask: DisposablePdfLoadingTask | null
  clearReferences(): void
}

export async function disposePdfPreviewResources(resources: PdfPreviewResources): Promise<void> {
  try {
    resources.renderTask?.cancel()
  } catch {
    // Continue releasing the document even if cancellation itself fails.
  }
  try {
    await resources.renderTask?.promise
  } catch {
    // Cancellation rejects RenderTask.promise by design; it is now settled.
  }

  try {
    await resources.pdfDocument?.cleanup()
  } catch {
    // Loading-task destruction below is authoritative and must still run.
  } finally {
    try {
      await resources.loadingTask?.destroy()
    } catch {
      // Replacement must continue even when the old worker is already gone.
    } finally {
      resources.clearReferences()
    }
  }
}

export interface PreviewMetricsInput {
  containerWidth: number
  containerHeight: number
  viewportWidth: number
  viewportHeight: number
  devicePixelRatio: number
}

export interface PreviewMetrics extends PreviewMetricsInput {
  drawerWidth: number
}

function nonNegativeFinite(value: number): number {
  return Number.isFinite(value) ? Math.max(0, value) : 0
}

export function normalizePreviewMetrics(input: PreviewMetricsInput): PreviewMetrics {
  const viewportWidth = nonNegativeFinite(input.viewportWidth)
  const devicePixelRatio = Number.isFinite(input.devicePixelRatio) && input.devicePixelRatio > 0
    ? input.devicePixelRatio
    : 1
  return {
    containerWidth: nonNegativeFinite(input.containerWidth),
    containerHeight: nonNegativeFinite(input.containerHeight),
    viewportWidth,
    viewportHeight: nonNegativeFinite(input.viewportHeight),
    devicePixelRatio,
    drawerWidth: Math.min(Math.max(viewportWidth - 20, 320), 720),
  }
}

export function previewMetricsRequireRender(previous: PreviewMetrics, next: PreviewMetrics): boolean {
  return previous.containerWidth !== next.containerWidth
    || previous.containerHeight !== next.containerHeight
    || previous.viewportWidth !== next.viewportWidth
    || previous.viewportHeight !== next.viewportHeight
    || previous.devicePixelRatio !== next.devicePixelRatio
}
