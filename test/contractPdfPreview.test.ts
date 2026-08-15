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

test('preview prefers a signed COS URL, keeps Range loading, and retains the authenticated fallback', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /pdf\.worker\.min\.mjs\?url/)
  assert.match(source, /pdfWorkerVersionedUrl/)
  assert.match(source, /previewPdfRequest\(props\.document\.versionId\)/)
  assert.match(source, /originalPdfRequest\(props\.document\.versionId\)/)
  assert.match(source, /rangeChunkSize:\s*512\s*\*\s*1024/)
  assert.match(source, /disableAutoFetch:\s*false/)
  assert.match(source, /disableStream:\s*false/)
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

test('preview observes its real container and names every symbol-only zoom action', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /resizeObserver\.observe\(previewContainerRef\.value\)/)
  assert.match(source, /watch\(previewMetrics/)
  assert.match(source, /devicePixelRatio\.value/)
  assert.match(source, /viewportWidth\.value/)
  assert.equal(source.match(/aria-label="缩小合同 PDF"/g)?.length, 2)
  assert.equal(source.match(/aria-label="放大合同 PDF"/g)?.length, 2)
})
