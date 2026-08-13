import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  clampPage,
  clampScale,
  createRenderTokenGuard,
  neighborPages,
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

test('preview loads the authenticated original with bounded Range requests and a worker URL', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /pdf\.worker\.min\.mjs\?url/)
  assert.match(source, /originalPdfRequest\(props\.document\.versionId\)/)
  assert.match(source, /rangeChunkSize:\s*256\s*\*\s*1024/)
  assert.match(source, /disableAutoFetch:\s*true/)
  assert.match(source, /disableStream:\s*true/)
})

test('preview replacement, download, idle prefetch, cleanup and drawer behavior stay local', () => {
  const source = readWorkspaceFile('src/components/project/ContractPdfPreview.vue')

  assert.match(source, /documentId:\s*props\.document\?\.documentId/)
  assert.match(source, /downloadOriginalPdf\(props\.document\.versionId\)/)
  assert.match(source, /requestIdleCallback/)
  assert.match(source, /renderTask[^\n]*\?\.cancel\(\)/)
  assert.match(source, /loadingTask[^\n]*\?\.destroy\(\)/)
  assert.match(source, /pdfDocument[^\n]*\?\.cleanup\(\)/)
  assert.match(source, /resizeObserver[^\n]*\?\.disconnect\(\)/)
  assert.match(source, /查看合同原文/)
  assert.match(source, /<ADrawer/)
})
