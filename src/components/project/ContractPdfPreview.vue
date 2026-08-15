<template>
  <div class="contract-pdf-preview" :class="{ 'contract-pdf-preview--narrow': isNarrow }">
    <button v-if="isNarrow" class="contract-pdf-preview__compact" type="button" @click="openDrawer">
      查看合同原文
      <span v-if="document" class="contract-pdf-preview__compact-name">{{ document.name }}</span>
    </button>

    <button
      v-else-if="collapsed"
      class="contract-pdf-preview__collapsed"
      type="button"
      @click="emit('update:collapsed', false)"
    >
      查看合同原文
    </button>

    <section v-else-if="!isNarrow" class="contract-pdf-preview__pane" aria-label="合同原文预览">
      <header class="contract-pdf-preview__header">
        <div class="contract-pdf-preview__heading">
          <strong>合同原文</strong>
          <span v-if="document" :title="document.name">{{ document.name }}</span>
          <span v-else>上传 PDF 后可在线逐页对照</span>
        </div>
        <div class="contract-pdf-preview__actions">
          <button type="button" :disabled="uploading" @click="chooseFile">
            {{ document ? '替换 PDF' : '上传 PDF' }}
          </button>
          <button v-if="document" type="button" :disabled="downloading" @click="downloadPdf">
            {{ downloading ? '下载中…' : '下载' }}
          </button>
          <button type="button" @click="emit('update:collapsed', true)">收起</button>
        </div>
      </header>

      <div ref="previewContainerRef" class="contract-pdf-preview__surface">
        <div v-if="!document" class="contract-pdf-preview__empty">
          <strong>请先上传施工合同 PDF</strong>
          <span>文件会按需加载，不会在后台生成整本页面图片。</span>
          <button type="button" @click="chooseFile">选择 PDF</button>
        </div>
        <div v-else ref="canvasScrollerRef" class="contract-pdf-preview__canvas-scroll">
          <canvas ref="canvasRef" aria-label="合同 PDF 当前页" />
        </div>

        <div v-if="paneBusy" class="contract-pdf-preview__overlay" aria-live="polite">
          <span class="contract-pdf-preview__spinner" />
          <strong>{{ busyLabel }}</strong>
          <small v-if="uploading">{{ uploadProgress }}%</small>
        </div>
        <div v-if="localError" class="contract-pdf-preview__error" role="alert">
          <span>{{ localError }}</span>
          <button v-if="document" type="button" @click="reloadDocument">重试</button>
        </div>
      </div>

      <footer v-if="document" class="contract-pdf-preview__toolbar">
        <button type="button" :disabled="page <= 1 || paneBusy" @click="setPage(page - 1)">上一页</button>
        <label>
          <span>第</span>
          <input
            :value="page"
            type="number"
            min="1"
            :max="Math.max(totalPages, 1)"
            aria-label="合同 PDF 页码"
            :disabled="paneBusy"
            @keydown.enter.prevent="setPage(Number(($event.target as HTMLInputElement).value))"
            @change="setPage(Number(($event.target as HTMLInputElement).value))"
          />
          <span>/ {{ totalPages || '—' }} 页</span>
        </label>
        <button type="button" :disabled="page >= totalPages || paneBusy" @click="setPage(page + 1)">下一页</button>
        <span class="contract-pdf-preview__toolbar-spacer" />
        <button aria-label="缩小合同 PDF" type="button" :disabled="scale <= 0.5 || paneBusy" @click="setScale(scale - 0.1)">−</button>
        <span>{{ Math.round(scale * 100) }}%</span>
        <button aria-label="放大合同 PDF" type="button" :disabled="scale >= 2.5 || paneBusy" @click="setScale(scale + 0.1)">＋</button>
      </footer>
    </section>

    <ADrawer
      v-if="isNarrow"
      :visible="drawerVisible"
      :width="drawerWidth"
      :footer="false"
      :mask-closable="true"
      :unmount-on-close="false"
      placement="right"
      @update:visible="setDrawerVisible"
      @cancel="setDrawerVisible(false)"
    >
      <template #title>合同原文</template>
      <div class="contract-pdf-preview__drawer-body">
        <header class="contract-pdf-preview__header">
          <div class="contract-pdf-preview__heading">
            <strong>{{ document?.name || '尚未上传合同 PDF' }}</strong>
            <span v-if="document">{{ formatFileSize(document.fileSize) }}</span>
          </div>
          <div class="contract-pdf-preview__actions">
            <button type="button" :disabled="uploading" @click="chooseFile">
              {{ document ? '替换 PDF' : '上传 PDF' }}
            </button>
            <button v-if="document" type="button" :disabled="downloading" @click="downloadPdf">
              {{ downloading ? '下载中…' : '下载' }}
            </button>
          </div>
        </header>

        <div ref="previewContainerRef" class="contract-pdf-preview__surface contract-pdf-preview__surface--drawer">
          <div v-if="!document" class="contract-pdf-preview__empty">
            <strong>请先上传施工合同 PDF</strong>
            <span>仅支持 PDF，上传失败不会替换当前合同。</span>
            <button type="button" @click="chooseFile">选择 PDF</button>
          </div>
          <div v-else ref="canvasScrollerRef" class="contract-pdf-preview__canvas-scroll">
            <canvas ref="canvasRef" aria-label="合同 PDF 当前页" />
          </div>

          <div v-if="paneBusy" class="contract-pdf-preview__overlay" aria-live="polite">
            <span class="contract-pdf-preview__spinner" />
            <strong>{{ busyLabel }}</strong>
            <small v-if="uploading">{{ uploadProgress }}%</small>
          </div>
          <div v-if="localError" class="contract-pdf-preview__error" role="alert">
            <span>{{ localError }}</span>
            <button v-if="document" type="button" @click="reloadDocument">重试</button>
          </div>
        </div>

        <footer v-if="document" class="contract-pdf-preview__toolbar">
          <button type="button" :disabled="page <= 1 || paneBusy" @click="setPage(page - 1)">上一页</button>
          <label>
            <input
              :value="page"
              type="number"
              min="1"
              :max="Math.max(totalPages, 1)"
              aria-label="合同 PDF 页码"
              :disabled="paneBusy"
              @keydown.enter.prevent="setPage(Number(($event.target as HTMLInputElement).value))"
              @change="setPage(Number(($event.target as HTMLInputElement).value))"
            />
            <span>/ {{ totalPages || '—' }}</span>
          </label>
          <button type="button" :disabled="page >= totalPages || paneBusy" @click="setPage(page + 1)">下一页</button>
          <span class="contract-pdf-preview__toolbar-spacer" />
          <button aria-label="缩小合同 PDF" type="button" :disabled="scale <= 0.5 || paneBusy" @click="setScale(scale - 0.1)">−</button>
          <span>{{ Math.round(scale * 100) }}%</span>
          <button aria-label="放大合同 PDF" type="button" :disabled="scale >= 2.5 || paneBusy" @click="setScale(scale + 0.1)">＋</button>
        </footer>
      </div>
    </ADrawer>

    <input ref="fileInputRef" class="contract-pdf-preview__file-input" type="file" accept=".pdf,application/pdf" @change="uploadSelectedFile" />
  </div>
</template>

<script setup lang="ts">
import { Drawer as ADrawer } from '@arco-design/web-vue'
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentLoadingTask,
  type PDFDocumentProxy,
  type RenderTask,
} from 'pdfjs-dist'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import {
  downloadOriginalPdf,
  originalPdfRequest,
  previewPdfRequest,
  uploadDocument,
} from '@/api/documentReview'
import {
  clampPage,
  clampScale,
  createRenderTokenGuard,
  disposePdfPreviewResources,
  neighborPages,
  normalizePreviewMetrics,
  previewMetricsRequireRender,
  type PreviewMetrics,
} from '@/utils/contractPdfPreview'
import { friendlyErrorMessage } from '@/utils/errors'

// The worker is served as an immutable hashed asset. Bump this query version
// when its response headers change so browsers do not reuse a cached worker
// response with the old MIME type.
const pdfWorkerVersionedUrl = `${pdfWorkerUrl}${pdfWorkerUrl.includes('?') ? '&' : '?'}v=2`
GlobalWorkerOptions.workerSrc = pdfWorkerVersionedUrl

export type ContractDocumentRef = {
  documentId: string
  versionId: string
  name: string
  mimeType: string
  fileSize: number
}

const props = defineProps<{
  document: ContractDocumentRef | null
  maxFileSizeMb: number
  page: number
  scale: number
  collapsed: boolean
}>()

const emit = defineEmits<{
  uploaded: [document: ContractDocumentRef]
  'update:page': [page: number]
  'update:scale': [scale: number]
  'update:collapsed': [collapsed: boolean]
  uploading: [uploading: boolean]
  error: [message: string]
}>()

const previewContainerRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasScrollerRef = ref<HTMLElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const pdfDocument = shallowRef<PDFDocumentProxy | null>(null)
const totalPages = ref(0)
const localLoading = ref(false)
const localRendering = ref(false)
const localError = ref('')
const uploading = ref(false)
const downloading = ref(false)
const uploadProgress = ref(0)
const drawerVisible = ref(false)
const renderTokens = createRenderTokenGuard()
const prefetchedPages = new Set<number>()
const previewMetrics = ref<PreviewMetrics>(normalizePreviewMetrics({
  containerWidth: 0,
  containerHeight: 0,
  viewportWidth: window.innerWidth,
  viewportHeight: window.innerHeight,
  devicePixelRatio: window.devicePixelRatio,
}))

let loadingTask: PDFDocumentLoadingTask | null = null
let renderTask: RenderTask | null = null
let resizeObserver: ResizeObserver | null = null
let dprMediaQuery: MediaQueryList | null = null
let disposalPromise: Promise<void> | null = null
let documentGeneration = 0
let idleHandle: number | null = null
let idleHandleKind: 'idle' | 'timeout' | null = null

const paneBusy = computed(() => localLoading.value || localRendering.value || uploading.value || downloading.value)
const busyLabel = computed(() => {
  if (uploading.value) return props.document ? '正在替换合同 PDF' : '正在上传合同 PDF'
  if (downloading.value) return '正在准备下载'
  if (localLoading.value) return '正在按需加载合同原文'
  return '正在渲染当前页'
})
const viewportWidth = computed(() => previewMetrics.value.viewportWidth)
const devicePixelRatio = computed(() => previewMetrics.value.devicePixelRatio)
const drawerWidth = computed(() => previewMetrics.value.drawerWidth)
const isNarrow = computed(() => viewportWidth.value < 960)

watch(
  () => props.document?.versionId || '',
  () => {
    void loadDocument()
  },
  { immediate: true, flush: 'post' },
)

watch(
  () => [props.page, props.scale] as const,
  () => {
    if (!pdfDocument.value) return
    void renderCurrentPage()
  },
)

watch(isNarrow, (narrow) => {
  if (!narrow) drawerVisible.value = false
})

watch(previewMetrics, async (next, previous) => {
  if (!previewMetricsRequireRender(previous, next)) return
  await nextTick()
  if (pdfDocument.value && previewIsVisible()) void renderCurrentPage()
})

watch(previewContainerRef, (current, previous) => {
  if (previous) resizeObserver?.unobserve(previous)
  if (!current) return
  resizeObserver?.observe(current)
  updatePreviewMetrics(current.getBoundingClientRect())
}, { flush: 'post' })

function handleObservedResize(entries: ResizeObserverEntry[]) {
  const current = previewContainerRef.value
  const entry = entries.find((candidate) => candidate.target === current)
  updatePreviewMetrics(entry?.contentRect)
}

function handleViewportChange() {
  updatePreviewMetrics()
}

function handleDprChange() {
  updatePreviewMetrics()
}

onMounted(() => {
  resizeObserver = new ResizeObserver(handleObservedResize)
  if (previewContainerRef.value) resizeObserver.observe(previewContainerRef.value)
  window.addEventListener('resize', handleViewportChange)
  bindDprMediaQuery()
  updatePreviewMetrics()
})

onBeforeUnmount(() => {
  documentGeneration += 1
  cancelIdlePrefetch()
  renderTokens.invalidate()
  void disposePdfDocument()
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('resize', handleViewportChange)
  dprMediaQuery?.removeEventListener('change', handleDprChange)
  dprMediaQuery = null
  clearCanvas()
})

function updatePreviewMetrics(size?: Pick<DOMRectReadOnly, 'width' | 'height'>) {
  const measured = size || previewContainerRef.value?.getBoundingClientRect()
  const previous = previewMetrics.value
  const next = normalizePreviewMetrics({
    containerWidth: measured?.width || 0,
    containerHeight: measured?.height || 0,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
  })
  if (!previewMetricsRequireRender(previous, next)) return
  previewMetrics.value = next
  if (previous.devicePixelRatio !== next.devicePixelRatio) bindDprMediaQuery()
}

function bindDprMediaQuery() {
  dprMediaQuery?.removeEventListener('change', handleDprChange)
  dprMediaQuery = window.matchMedia(`(resolution: ${devicePixelRatio.value}dppx)`)
  dprMediaQuery.addEventListener('change', handleDprChange)
}

function previewIsVisible() {
  return isNarrow.value ? drawerVisible.value : !props.collapsed
}

function openDrawer() {
  drawerVisible.value = true
  void nextTick(() => {
    if (pdfDocument.value) void renderCurrentPage()
  })
}

function setDrawerVisible(visible: boolean) {
  drawerVisible.value = visible
  if (visible) {
    void nextTick(() => {
      if (pdfDocument.value) void renderCurrentPage()
    })
  }
}

function chooseFile() {
  fileInputRef.value?.click()
}

async function uploadSelectedFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  input.value = ''
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    publishError('仅支持上传 PDF 格式的合同文件。')
    return
  }
  const maxBytes = Math.max(0, props.maxFileSizeMb) * 1024 * 1024
  if (maxBytes > 0 && file.size > maxBytes) {
    publishError(`合同 PDF 不能超过 ${props.maxFileSizeMb}MB。`)
    return
  }

  uploading.value = true
  uploadProgress.value = 0
  localError.value = ''
  emit('uploading', true)
  try {
    const result = await uploadDocument(
      {
        file,
        documentType: 'construction_contract',
        lifecycleStage: 'contract_handoff',
        documentId: props.document?.documentId,
      },
      (percent) => {
        uploadProgress.value = percent
      },
    )
    emit('uploaded', {
      documentId: result.document.id,
      versionId: result.version.id,
      name: result.version.name,
      mimeType: result.version.mimeType,
      fileSize: result.version.fileSize,
    })
  } catch (error) {
    publishError(friendlyErrorMessage(error, '合同 PDF 上传失败，原文件已保留，请稍后重试。'))
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    emit('uploading', false)
  }
}

async function downloadPdf() {
  if (!props.document || downloading.value) return
  downloading.value = true
  localError.value = ''
  try {
    const blob = await downloadOriginalPdf(props.document.versionId)
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = props.document.name || 'contract.pdf'
    link.style.display = 'none'
    window.document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    publishError(friendlyErrorMessage(error, '合同 PDF 下载失败，请稍后重试。'))
  } finally {
    downloading.value = false
  }
}

function setPage(nextPage: number) {
  const next = clampPage(nextPage, totalPages.value || 1)
  if (next !== props.page) emit('update:page', next)
}

function setScale(nextScale: number) {
  const next = clampScale(nextScale)
  if (next !== props.scale) emit('update:scale', next)
}

function reloadDocument() {
  void loadDocument()
}

async function loadDocument() {
  const generation = ++documentGeneration
  await disposePdfDocument()
  localError.value = ''
  totalPages.value = 0
  clearCanvas()

  if (!props.document) {
    localLoading.value = false
    return
  }

  localLoading.value = true
  let request = await previewPdfRequest(props.document.versionId)
  if (generation !== documentGeneration) return
  const createLoadingTask = () => getDocument({
    ...request,
    rangeChunkSize: 512 * 1024,
    disableAutoFetch: false,
    disableStream: false,
  })
  let task = createLoadingTask()
  loadingTask = task
  try {
    let loaded: PDFDocumentProxy
    try {
      loaded = await task.promise
    } catch (error) {
      if (!request.direct || generation !== documentGeneration || isCancellation(error)) throw error
      try {
        await task.destroy()
      } catch {
        // The failed direct task may already be settled.
      }
      request = originalPdfRequest(props.document.versionId)
      task = createLoadingTask()
      loadingTask = task
      loaded = await task.promise
    }
    if (generation !== documentGeneration) {
      if (loadingTask === task) loadingTask = null
      try {
        await task.destroy()
      } catch {
        // A concurrent replacement may already have destroyed this worker.
      }
      return
    }
    pdfDocument.value = loaded
    totalPages.value = loaded.numPages
    prefetchedPages.clear()
    const safePage = clampPage(props.page, loaded.numPages)
    if (safePage !== props.page) emit('update:page', safePage)
    await nextTick()
    if (!isNarrow.value || drawerVisible.value) await renderCurrentPage(safePage)
  } catch (error) {
    if (loadingTask === task) {
      loadingTask = null
      try {
        await task.destroy()
      } catch {
        // Preserve the original load failure and allow a later replacement.
      }
    }
    if (generation !== documentGeneration || isCancellation(error)) return
    publishError(friendlyErrorMessage(error, '合同 PDF 已上传，但原文预览加载失败，请点击“重试”或下载查看。'))
  } finally {
    if (generation === documentGeneration) localLoading.value = false
  }
}

async function disposePdfDocument() {
  if (disposalPromise) return disposalPromise
  cancelIdlePrefetch()
  renderTokens.invalidate()
  const activeRenderTask = renderTask
  const activePdfDocument = pdfDocument.value
  const activeLoadingTask = loadingTask
  const run = disposePdfPreviewResources({
    renderTask: activeRenderTask,
    pdfDocument: activePdfDocument,
    loadingTask: activeLoadingTask,
    clearReferences() {
      if (renderTask === activeRenderTask) renderTask = null
      if (pdfDocument.value === activePdfDocument) pdfDocument.value = null
      if (loadingTask === activeLoadingTask) loadingTask = null
      localRendering.value = false
      prefetchedPages.clear()
    },
  })
  disposalPromise = run.finally(() => {
    disposalPromise = null
  })
  return disposalPromise
}

async function renderCurrentPage(explicitPage?: number) {
  if (disposalPromise) return
  const loaded = pdfDocument.value
  const visibleCanvas = canvasRef.value
  if (!loaded || !visibleCanvas) return

  const currentPage = clampPage(explicitPage ?? props.page, loaded.numPages)
  const currentScale = clampScale(props.scale)
  const token = renderTokens.next()
  renderTask?.cancel()
  renderTask = null
  cancelIdlePrefetch()
  localRendering.value = true
  localError.value = ''

  try {
    const pageProxy = await loaded.getPage(currentPage)
    if (!renderTokens.isCurrent(token) || loaded !== pdfDocument.value) return
    const viewport = pageProxy.getViewport({ scale: currentScale })
    const outputScale = Math.max(1, devicePixelRatio.value)
    const stagingCanvas = window.document.createElement('canvas')
    stagingCanvas.width = Math.max(1, Math.floor(viewport.width * outputScale))
    stagingCanvas.height = Math.max(1, Math.floor(viewport.height * outputScale))
    const stagingContext = stagingCanvas.getContext('2d', { alpha: false })
    if (!stagingContext) throw new Error('浏览器无法创建 PDF 画布。')

    const task = pageProxy.render({
      canvas: stagingCanvas,
      canvasContext: stagingContext,
      viewport,
      transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
    })
    renderTask = task
    await task.promise
    if (!renderTokens.isCurrent(token) || loaded !== pdfDocument.value) return

    visibleCanvas.width = stagingCanvas.width
    visibleCanvas.height = stagingCanvas.height
    visibleCanvas.style.width = `${Math.floor(viewport.width)}px`
    visibleCanvas.style.height = `${Math.floor(viewport.height)}px`
    const visibleContext = visibleCanvas.getContext('2d', { alpha: false })
    if (!visibleContext) throw new Error('浏览器无法显示 PDF 画布。')
    visibleContext.drawImage(stagingCanvas, 0, 0)
    scheduleNeighborPrefetch(currentPage, loaded)
  } catch (error) {
    if (!isCancellation(error) && renderTokens.isCurrent(token)) {
      publishError(friendlyErrorMessage(error, '当前合同页面渲染失败，请重试。'))
    }
  } finally {
    if (renderTokens.isCurrent(token)) {
      renderTask = null
      localRendering.value = false
    }
  }
}

function scheduleNeighborPrefetch(currentPage: number, loaded: PDFDocumentProxy) {
  cancelIdlePrefetch()
  const pages = neighborPages(currentPage, loaded.numPages).filter(
    (candidate) => candidate !== currentPage && !prefetchedPages.has(candidate),
  )
  if (!pages.length) return

  const prefetch = async () => {
    idleHandle = null
    idleHandleKind = null
    for (const candidate of pages) {
      if (loaded !== pdfDocument.value) return
      try {
        await loaded.getPage(candidate)
        if (loaded === pdfDocument.value) prefetchedPages.add(candidate)
      } catch {
        // Prefetch is best-effort and must not affect the active page.
      }
    }
  }

  if ('requestIdleCallback' in window) {
    idleHandleKind = 'idle'
    idleHandle = window.requestIdleCallback(() => {
      void prefetch()
    }, { timeout: 800 })
  } else {
    idleHandleKind = 'timeout'
    idleHandle = globalThis.setTimeout(() => {
      void prefetch()
    }, 0)
  }
}

function cancelIdlePrefetch() {
  if (idleHandle === null) return
  if (idleHandleKind === 'idle' && 'cancelIdleCallback' in window) window.cancelIdleCallback(idleHandle)
  else window.clearTimeout(idleHandle)
  idleHandle = null
  idleHandleKind = null
}

function clearCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const context = canvas.getContext('2d')
  context?.clearRect(0, 0, canvas.width, canvas.height)
  canvas.width = 0
  canvas.height = 0
  canvas.style.width = ''
  canvas.style.height = ''
  canvasScrollerRef.value?.scrollTo({ top: 0, left: 0 })
}

function publishError(message: string) {
  localError.value = message
  emit('error', message)
}

function isCancellation(error: unknown) {
  return error instanceof Error && (error.name === 'RenderingCancelledException' || error.name === 'AbortException')
}

function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.contract-pdf-preview {
  min-width: 0;
  height: 100%;
  color: var(--color-text-1);
}

.contract-pdf-preview__pane,
.contract-pdf-preview__drawer-body {
  display: flex;
  min-height: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border-2);
  border-radius: 12px;
  background: var(--color-bg-2);
}

.contract-pdf-preview__drawer-body {
  height: calc(100vh - 112px);
  border: 0;
  border-radius: 0;
}

.contract-pdf-preview__header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border-2);
}

.contract-pdf-preview__heading {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.contract-pdf-preview__heading strong {
  font-size: 15px;
}

.contract-pdf-preview__heading span {
  overflow: hidden;
  color: var(--color-text-3);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contract-pdf-preview__actions {
  display: flex;
  flex: 0 0 auto;
  gap: 6px;
}

.contract-pdf-preview button {
  min-height: 30px;
  padding: 5px 10px;
  border: 1px solid var(--color-border-3);
  border-radius: 6px;
  color: var(--color-text-1);
  background: var(--color-bg-2);
  cursor: pointer;
}

.contract-pdf-preview button:hover:not(:disabled) {
  border-color: rgb(var(--primary-6));
  color: rgb(var(--primary-6));
}

.contract-pdf-preview button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.contract-pdf-preview__surface {
  position: relative;
  display: flex;
  min-height: 280px;
  flex: 1 1 auto;
  overflow: hidden;
  background: var(--color-fill-2);
}

.contract-pdf-preview__surface--drawer {
  min-height: 0;
}

.contract-pdf-preview__canvas-scroll {
  width: 100%;
  height: 100%;
  padding: 20px;
  overflow: auto;
  text-align: center;
}

.contract-pdf-preview__canvas-scroll canvas {
  display: inline-block;
  max-width: none;
  border-radius: 2px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(24, 35, 52, 0.16);
}

.contract-pdf-preview__empty {
  display: grid;
  max-width: 360px;
  margin: auto;
  justify-items: center;
  gap: 10px;
  padding: 28px;
  color: var(--color-text-3);
  text-align: center;
}

.contract-pdf-preview__empty strong {
  color: var(--color-text-1);
}

.contract-pdf-preview__overlay,
.contract-pdf-preview__error {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 8px;
  padding: 24px;
  text-align: center;
}

.contract-pdf-preview__overlay {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(2px);
}

.contract-pdf-preview__error {
  z-index: 3;
  color: rgb(var(--danger-6));
  background: rgba(255, 247, 247, 0.94);
}

.contract-pdf-preview__spinner {
  width: 26px;
  height: 26px;
  border: 3px solid var(--color-border-2);
  border-top-color: rgb(var(--primary-6));
  border-radius: 50%;
  animation: contract-pdf-spin 0.8s linear infinite;
}

.contract-pdf-preview__toolbar {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-top: 1px solid var(--color-border-2);
  background: var(--color-bg-1);
}

.contract-pdf-preview__toolbar button {
  min-width: 30px;
  min-height: 30px;
}

.contract-pdf-preview__toolbar label {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--color-text-2);
  font-size: 12px;
}

.contract-pdf-preview__toolbar input {
  width: 54px;
  height: 30px;
  border: 1px solid var(--color-border-3);
  border-radius: 6px;
  color: var(--color-text-1);
  background: var(--color-bg-1);
  text-align: center;
}

.contract-pdf-preview__toolbar-spacer {
  flex: 1 1 auto;
}

.contract-pdf-preview__compact,
.contract-pdf-preview__collapsed {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-style: dashed !important;
  color: rgb(var(--primary-6)) !important;
}

.contract-pdf-preview__collapsed {
  height: 100%;
  min-height: 180px !important;
  writing-mode: vertical-rl;
}

.contract-pdf-preview__compact-name {
  max-width: 52vw;
  overflow: hidden;
  color: var(--color-text-3);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.contract-pdf-preview__file-input {
  display: none;
}

@keyframes contract-pdf-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .contract-pdf-preview__spinner { animation: none; }
}
</style>
