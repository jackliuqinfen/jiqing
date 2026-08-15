import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  clampPage,
  clampScale,
  createRenderTokenGuard,
  disposePdfPreviewResources,
  neighborPages,
  normalizePreviewMetrics,
  previewMetricsRequireRender,
} from '../src/utils/contractPdfPreview.ts'
import * as previewUtils from '../src/utils/contractPdfPreview.ts'

const readWorkspaceFile = (relativePath: string) =>
  readFileSync(fileURLToPath(new URL(`../${relativePath}`, import.meta.url)), 'utf8')

test('neighborPages returns the current page and only adjacent valid pages', () => {
  assert.deepEqual(neighborPages(1, 57), [1, 2])
  assert.deepEqual(neighborPages(28, 57), [27, 28, 29])
  assert.deepEqual(neighborPages(57, 57), [56, 57])
  assert.deepEqual(neighborPages(1, 0), [])
})

test('clampPage keeps page requests within the loaded document', () => {
  assert.equal(clampPage(99, 57), 57)
  assert.equal(clampPage(-5, 57), 1)
  assert.equal(clampPage(Number.NaN, 57), 1)
})

test('clampScale keeps zoom requests within the supported range', () => {
  assert.equal(clampScale(0.1), 0.5)
  assert.equal(clampScale(3), 2.5)
  assert.equal(clampScale(1.237), 1.24)
  assert.equal(clampScale(Number.NaN), 1)
})

test('render token guard rejects stale asynchronous publishes', () => {
  const tokens = createRenderTokenGuard()
  const firstRender = tokens.next()

  assert.equal(tokens.isCurrent(firstRender), true)

  const secondRender = tokens.next()
  assert.ok(secondRender > firstRender)
  assert.equal(tokens.isCurrent(firstRender), false)
  assert.equal(tokens.isCurrent(secondRender), true)

  tokens.invalidate()
  assert.equal(tokens.isCurrent(secondRender), false)
})

test('disposal waits for canceled rendering and still destroys and clears after cleanup failures', async () => {
  const order: string[] = []
  let rejectRender!: (error: Error) => void
  const renderPromise = new Promise<void>((_resolve, reject) => {
    rejectRender = (error) => {
      order.push('render-settled')
      reject(error)
    }
  })

  const disposal = disposePdfPreviewResources({
    renderTask: {
      cancel() {
        order.push('cancel')
      },
      promise: renderPromise,
    },
    pdfDocument: {
      async cleanup() {
        order.push('cleanup')
        throw new Error('startCleanup: page is currently rendering')
      },
    },
    loadingTask: {
      async destroy() {
        order.push('destroy')
        throw new Error('worker already stopped')
      },
    },
    clearReferences() {
      order.push('clear')
    },
  })

  await Promise.resolve()
  assert.deepEqual(order, ['cancel'])

  rejectRender(new Error('Rendering cancelled'))
  await disposal

  assert.deepEqual(order, ['cancel', 'render-settled', 'cleanup', 'destroy', 'clear'])
})

test('preview metrics normalize viewport state and invalidate rendering on size or DPR changes', () => {
  const initial = normalizePreviewMetrics({
    containerWidth: 620.5,
    containerHeight: 700,
    viewportWidth: 900,
    viewportHeight: 800,
    devicePixelRatio: 1,
  })
  const resized = normalizePreviewMetrics({
    containerWidth: 640,
    containerHeight: 700,
    viewportWidth: 920,
    viewportHeight: 800,
    devicePixelRatio: 1,
  })
  const movedToRetina = normalizePreviewMetrics({
    ...resized,
    devicePixelRatio: 2,
  })

  assert.equal(initial.drawerWidth, 720)
  assert.equal(normalizePreviewMetrics({ ...initial, viewportWidth: 500 }).drawerWidth, 480)
  assert.equal(normalizePreviewMetrics({ ...initial, devicePixelRatio: 0 }).devicePixelRatio, 1)
  assert.equal(previewMetricsRequireRender(initial, resized), true)
  assert.equal(previewMetricsRequireRender(resized, movedToRetina), true)
  assert.equal(previewMetricsRequireRender(resized, { ...resized }), false)
})

test('preview fit modes keep an A4 page inside the real canvas viewport', () => {
  const resolvePreviewScale = previewUtils['resolvePreviewScale']
  assert.equal(typeof resolvePreviewScale, 'function')

  const base = {
    pageWidth: 595,
    pageHeight: 842,
    containerWidth: 550,
    containerHeight: 590,
    padding: 40,
    requestedScale: 1,
  }

  assert.equal(resolvePreviewScale({ ...base, mode: 'page' }), 0.65)
  assert.equal(resolvePreviewScale({ ...base, mode: 'width' }), 0.86)
  assert.equal(resolvePreviewScale({ ...base, mode: 'custom', requestedScale: 1.25 }), 1.25)
})

test('PDF.js stays exactly pinned and is split before the generic vendor chunk', () => {
  const packageJson = JSON.parse(readWorkspaceFile('package.json')) as {
    dependencies: Record<string, string>
  }
  const viteConfig = readWorkspaceFile('vite.config.ts')

  assert.equal(packageJson.dependencies['pdfjs-dist'], '6.2.108')
  assert.match(
    viteConfig,
    /id\.includes\(['"]pdfjs-dist['"]\)[\s\S]*?return ['"]vendor-pdfjs['"]/,
  )
  assert.ok(viteConfig.indexOf("id.includes('pdfjs-dist')") < viteConfig.indexOf("id.includes('node_modules')"))
})

test('preview uses an authenticated PDF blob for native browser rendering', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /pdf\.worker\.min\.mjs\?url/)
  assert.match(source, /pdfWorkerVersionedUrl/)
  assert.match(source, /downloadOriginalPdf\(props\.document\.versionId\)/)
  assert.match(source, /new Blob\(\[await blob\.arrayBuffer\(\)\],\s*\{ type: 'application\/pdf' \}\)/)
  assert.match(source, /getDocument\(\{[\s\S]*?data:\s*documentData[\s\S]*?\}\)/)
})

test('preview replacement, download, idle prefetch, cleanup and drawer behavior stay local', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /documentId:\s*props\.document\?\.documentId/)
  assert.match(source, /downloadOriginalPdf\(props\.document\.versionId\)/)
  assert.match(source, /requestIdleCallback/)
  assert.match(source, /renderTask[^\n]*\?\.cancel\(\)/)
  assert.match(source, /resizeObserver[^\n]*\?\.disconnect\(\)/)
  assert.match(source, /查看合同原文/)
  assert.match(source, /<ADrawer/)
})

test('preview renders directly into the visible canvas with alpha compositing', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /canvas:\s*visibleCanvas/)
  assert.match(source, /canvasContext:\s*visibleContext/)
  assert.match(source, /getContext\('2d',\s*\{ alpha: true \}\)/)
  assert.match(source, /background:\s*'#fff'/)
  assert.doesNotMatch(source, /stagingCanvas/)
})

test('preview uses the browser PDF engine as the fidelity-first display path', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.equal(source.match(/class="contract-pdf-preview__native-frame"/g)?.length, 2)
  assert.match(source, /downloadOriginalPdf\(props\.document\.versionId\)/)
  assert.match(source, /nativePreviewSrc/)
  assert.match(source, /#page=\$\{safePage\}&zoom=\$\{safeZoom\}/)
  assert.match(source, /browser's native PDF viewer can still display/)
})

test('preview observes its real container and names every symbol-only zoom action', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /resizeObserver\.observe\(previewContainerRef\.value\)/)
  assert.match(source, /watch\(previewMetrics/)
  assert.match(source, /devicePixelRatio\.value/)
  assert.match(source, /viewportWidth\.value/)
  assert.equal(source.match(/aria-label="缩小合同 PDF"/g)?.length, 2)
  assert.equal(source.match(/aria-label="放大合同 PDF"/g)?.length, 2)
})

test('preview keeps the page controls reachable and supports Enter page navigation', () => {
  const previewSource = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')
  const projectSource = readWorkspaceFile('src/views/ProjectManagementView.vue')

  assert.equal(previewSource.match(/aria-label="合同 PDF 页码"/g)?.length, 2)
  assert.equal(previewSource.match(/@keydown\.enter\.prevent="setPage\(/g)?.length, 2)
  assert.match(projectSource, /\.project-create-shell\s*\{[\s\S]*height:\s*min\(70vh,\s*740px\);[\s\S]*overflow:\s*hidden;/)
  assert.match(projectSource, /\.project-create-shell__form,[\s\S]*\.project-create-shell__preview\s*\{[\s\S]*min-height:\s*0;/)
})

test('manual wizard gives the PDF half the width and hides the draft strip', () => {
  const previewSource = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')
  const projectSource = readWorkspaceFile('src/views/ProjectManagementView.vue')

  assert.match(previewSource, /ref<PreviewScaleMode>\('page'\)/)
  assert.equal(previewSource.match(/适应整页/g)?.length, 2)
  assert.equal(previewSource.match(/适应宽度/g)?.length, 2)
  assert.match(
    projectSource,
    /\.project-create-shell\s*\{[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\)\s+minmax\(0, 1fr\);/,
  )
  assert.doesNotMatch(projectSource, /manual-draft-strip/)
  assert.doesNotMatch(projectSource, /project-create-shell__preview--with-drafts/)
  assert.match(
    projectSource,
    /\.project-create-shell__preview\s*\{[\s\S]*grid-template-rows:\s*minmax\(0,\s*1fr\)/,
  )
})

test('preview floats navigation tools inside the bottom of the PDF surface', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')
  const toolbarMatches = [...source.matchAll(/class="contract-pdf-preview__toolbar"/g)]
  const surfaceMatches = [...source.matchAll(/class="contract-pdf-preview__surface(?:\s[^\"]*)?"/g)]

  assert.equal(toolbarMatches.length, 2)
  assert.equal(surfaceMatches.length, 2)
  assert.ok(toolbarMatches[0].index! > surfaceMatches[0].index!)
  assert.ok(toolbarMatches[1].index! > surfaceMatches[1].index!)
  assert.match(
    source,
    /\.contract-pdf-preview__toolbar\s*\{[\s\S]*position:\s*absolute;[\s\S]*bottom:/,
  )
  assert.match(source, /\.contract-pdf-preview__toolbar\s*\{[\s\S]*z-index:/)
  assert.match(source, /backdrop-filter:\s*blur\(/)
})
