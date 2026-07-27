import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import {
  chmodSync,
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { SyncApiError } from '../src/sync/api-client.mjs'
import { SyncEngine } from '../src/sync/sync-engine.mjs'

const ORIGIN = 'https://erp.example.cn'
const PROJECT_REF = 'project:p-1'

function digest(content) {
  return createHash('sha256').update(content).digest('hex')
}

function entry(revision, content, overrides = {}) {
  const sourceId = overrides.sourceId || 'doc-1'
  return {
    projectRef: PROJECT_REF,
    projectCode: '20260727-JQ-001',
    projectName: '区直学校维修',
    sourceType: 'project_file',
    sourceId,
    sourceRevision: revision,
    originalName: '施工合同.pdf',
    displayName: '施工合同.pdf',
    categoryKey: 'contract',
    categoryName: '合同文件',
    versionNo: 1,
    fileSize: content.length,
    sha256: digest(content),
    availability: 'available',
    downloadPath: `/api/desktop/sync/files/project_file/${sourceId}/download?revision=${revision}`,
    _content: content,
    ...overrides,
  }
}

class FakeApiClient {
  constructor({
    manifests,
    policy = {},
    downloadGate = null,
  }) {
    this.manifests = manifests
    this.policy = {
      enabled: true,
      enabledForCurrentUser: true,
      maxFileSizeBytes: 1024 * 1024,
      maxLocalStorageBytes: 1024 * 1024,
      policyVersion: 1,
      ...policy,
    }
    this.downloadGate = downloadGate
    this.downloadCalls = 0
    this.manifestCalls = []
    this.policyCalls = 0
    this.activeDownloads = 0
    this.maximumActiveDownloads = 0
    this.run = 0
    this.aborted = false
    this.contentByPath = new Map()
    for (const manifest of manifests) {
      for (const item of manifest) {
        this.contentByPath.set(item.downloadPath, item._content)
      }
    }
  }

  async getPolicy() {
    this.policyCalls += 1
    return { ...this.policy }
  }

  async getProjectRoots() {
    return [{
      projectRef: PROJECT_REF,
      canonicalProjectId: 'p-1',
      auditProjectId: null,
      projectCode: '20260727-JQ-001',
      projectName: '区直学校维修',
      fileCount: this.manifests[this.run]?.length || 0,
      totalFileSizeBytes: (this.manifests[this.run] || [])
        .reduce((total, item) => total + item.fileSize, 0),
    }]
  }

  async getManifest(_token, { cursor }) {
    this.manifestCalls.push(cursor)
    const items = this.manifests[Math.min(this.run, this.manifests.length - 1)]
    this.run += 1
    return {
      items: items.map(({ _content, ...item }) => item),
      nextCursor: `resume-${this.run}`,
      hasMore: false,
      policyVersion: this.policy.policyVersion,
    }
  }

  async download(_token, downloadPath, destinationPartPath, onProgress) {
    this.downloadCalls += 1
    this.activeDownloads += 1
    this.maximumActiveDownloads = Math.max(
      this.maximumActiveDownloads,
      this.activeDownloads,
    )
    try {
      await this.downloadGate?.()
      const content = this.contentByPath.get(downloadPath)
      await mkdir(join(destinationPartPath, '..'), { recursive: true })
      await writeFile(destinationPartPath, content)
      onProgress(content.length)
      return content.length
    } finally {
      this.activeDownloads -= 1
    }
  }

  abortAll() {
    this.aborted = true
  }
}

function createTestEngine(t, options) {
  const base = mkdtempSync(join(tmpdir(), 'jiqing-sync-engine-'))
  t.after(() => rmSync(base, { recursive: true, force: true }))
  const localRoot = join(base, 'visible')
  const appDataPath = join(base, 'app-data')
  const api = new FakeApiClient(options)
  const states = []
  const engine = new SyncEngine({
    apiClient: api,
    appDataPath,
    environmentOrigin: ORIGIN,
    now: () => new Date('2026-07-27T10:05:00.000Z'),
    emitState: (state) => states.push(state),
  })
  engine.setLocalRoot(localRoot)
  return {
    engine,
    api,
    states,
    localRoot,
    output(filename) {
      return join(
        localRoot,
        '20260727-JQ-001_区直学校维修',
        '合同文件',
        filename,
      )
    },
  }
}

function session() {
  return {
    authToken: 'memory-only-token',
    userId: 'user-1',
    projectRefs: [PROJECT_REF],
  }
}

test('downloads a verified file atomically and skips it on rerun', async (t) => {
  const content = Buffer.from('contract')
  const harness = createTestEngine(t, {
    manifests: [
      [entry('doc-1-v1', content)],
      [entry('doc-1-v1', content)],
    ],
  })

  await harness.engine.start(session())
  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'contract')
  assert.equal(harness.api.downloadCalls, 1)
  assert.equal(
    existsSync(join(
      harness.localRoot,
      '20260727-JQ-001_区直学校维修',
      '合同文件',
      '.jiqing-part-doc-1',
    )),
    false,
  )

  await harness.engine.start(session())
  assert.equal(harness.api.downloadCalls, 1)
  assert.deepEqual(harness.api.manifestCalls, ['', 'resume-1'])
})

test('restores an indexed missing file only on a later explicit start', async (t) => {
  const content = Buffer.from('contract')
  const harness = createTestEngine(t, {
    manifests: [
      [entry('doc-1-v1', content)],
      [entry('doc-1-v1', content)],
    ],
  })
  await harness.engine.start(session())
  chmodSync(harness.output('施工合同.pdf'), 0o666)
  unlinkSync(harness.output('施工合同.pdf'))
  assert.equal(existsSync(harness.output('施工合同.pdf')), false)

  await harness.engine.start(session())

  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'contract')
  assert.equal(harness.api.downloadCalls, 2)
})

test('never overwrites a locally modified file', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [
      [entry('doc-1-v1', Buffer.from('server-v1'))],
      [entry('doc-1-v2', Buffer.from('server-v2'))],
    ],
  })
  await harness.engine.start(session())
  chmodSync(harness.output('施工合同.pdf'), 0o666)
  writeFileSync(harness.output('施工合同.pdf'), 'local-change')

  await harness.engine.start(session())

  assert.equal(
    readFileSync(harness.output('施工合同.pdf'), 'utf8'),
    'local-change',
  )
  assert.equal(
    readFileSync(harness.output('施工合同_服务器新版.pdf'), 'utf8'),
    'server-v2',
  )
})

test('uses a deterministic numbered server filename when the conflict name exists', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [
      [entry('doc-1-v1', Buffer.from('server-v1'))],
      [entry('doc-1-v2', Buffer.from('server-v2'))],
    ],
  })
  await harness.engine.start(session())
  chmodSync(harness.output('施工合同.pdf'), 0o666)
  writeFileSync(harness.output('施工合同.pdf'), 'local-change')
  writeFileSync(harness.output('施工合同_服务器新版.pdf'), 'existing-copy')

  await harness.engine.start(session())

  assert.equal(
    readFileSync(harness.output('施工合同_服务器新版.pdf'), 'utf8'),
    'existing-copy',
  )
  assert.equal(
    readFileSync(harness.output('施工合同_服务器新版_2.pdf'), 'utf8'),
    'server-v2',
  )
})

test('keeps a server conflict filename within the Windows segment bound', async (t) => {
  const longName = `${'资'.repeat(76)}.pdf`
  const harness = createTestEngine(t, {
    manifests: [[entry('doc-1-v1', Buffer.from('server'), {
      originalName: longName,
    })]],
  })
  const directory = join(
    harness.localRoot,
    '20260727-JQ-001_区直学校维修',
    '合同文件',
  )
  await mkdir(directory, { recursive: true })
  writeFileSync(join(directory, longName), 'local-file')

  await harness.engine.start(session())

  const conflictName = readdirSync(directory)
    .find((name) => name.includes('服务器新版'))
  assert.ok(conflictName)
  assert.ok([...conflictName].length <= 80)
  assert.ok(conflictName.endsWith('_服务器新版.pdf'))
})

test('hash mismatch leaves no completed file', async (t) => {
  const content = Buffer.from('expected')
  const harness = createTestEngine(t, {
    manifests: [[entry('doc-1-v1', content, { sha256: '0'.repeat(64) })]],
  })

  await harness.engine.start(session())

  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
  assert.equal(harness.engine.getState().failedFiles, 1)
  assert.equal(harness.engine.getState().status, 'partial_failure')
})

test('processes no more than two downloads concurrently', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[
      entry('r-1', Buffer.from('one'), {
        sourceId: 'doc-1',
        originalName: '一.pdf',
      }),
      entry('r-2', Buffer.from('two'), {
        sourceId: 'doc-2',
        originalName: '二.pdf',
      }),
      entry('r-3', Buffer.from('three'), {
        sourceId: 'doc-3',
        originalName: '三.pdf',
      }),
    ]],
    downloadGate: () => new Promise((resolve) => setTimeout(resolve, 5)),
  })

  await harness.engine.start(session())

  assert.equal(harness.api.maximumActiveDownloads, 2)
  assert.equal(harness.engine.getState().completedFiles, 3)
})

test('emits in-progress downloaded bytes before completion', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
  })

  await harness.engine.start(session())

  assert.equal(
    harness.states.some((state) => (
      state.status === 'syncing'
      && state.bytesDownloaded === 8
      && state.completedFiles === 0
    )),
    true,
  )
  assert.equal(harness.engine.getState().bytesDownloaded, 8)
})

test('enforces file and total storage limits without creating oversized files', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[
      entry('r-1', Buffer.from('12345'), {
        sourceId: 'doc-1',
        originalName: '一.pdf',
      }),
      entry('r-2', Buffer.from('123456789'), {
        sourceId: 'doc-2',
        originalName: '二.pdf',
      }),
      entry('r-3', Buffer.from('67890'), {
        sourceId: 'doc-3',
        originalName: '三.pdf',
      }),
    ]],
    policy: {
      maxFileSizeBytes: 5,
      maxLocalStorageBytes: 5,
    },
  })

  await harness.engine.start(session())

  assert.equal(harness.api.downloadCalls, 1)
  assert.equal(harness.engine.getState().completedFiles, 1)
  assert.equal(harness.engine.getState().failedFiles, 2)
})

test('pause clears the token, aborts transfers, and wins over late completion', async (t) => {
  let releaseDownload
  const gate = new Promise((resolve) => {
    releaseDownload = resolve
  })
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
    downloadGate: () => gate,
  })

  const running = harness.engine.start(session())
  while (harness.api.activeDownloads === 0) {
    await new Promise((resolve) => setTimeout(resolve, 1))
  }
  const paused = harness.engine.pause()
  releaseDownload()
  await running

  assert.equal(paused.status, 'paused')
  assert.equal(harness.engine.getState().status, 'paused')
  assert.equal(harness.engine.hasActiveSession(), false)
  assert.equal(harness.api.aborted, true)
  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
})

test('maps permission loss to permission_changed without completed files', async (t) => {
  const harness = createTestEngine(t, { manifests: [[]] })
  harness.api.getPolicy = async () => {
    throw new SyncApiError('permission changed', 'permission_changed')
  }

  await harness.engine.start(session())

  assert.equal(harness.engine.getState().status, 'permission_changed')
  assert.equal(harness.engine.getState().completedFiles, 0)
})

test('re-fetches policy before downloading a manifest with a newer policy version', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
  })
  const originalManifest = harness.api.getManifest.bind(harness.api)
  harness.api.getManifest = async (...args) => ({
    ...await originalManifest(...args),
    policyVersion: 2,
  })
  harness.api.getPolicy = async () => {
    harness.api.policyCalls += 1
    return {
      ...harness.api.policy,
      policyVersion: harness.api.policyCalls === 1 ? 1 : 2,
    }
  }

  await harness.engine.start(session())

  assert.equal(harness.api.policyCalls, 2)
  assert.equal(harness.api.downloadCalls, 1)
})

test('does not download when a policy re-fetch remains behind the manifest', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
  })
  const originalManifest = harness.api.getManifest.bind(harness.api)
  harness.api.getManifest = async (...args) => ({
    ...await originalManifest(...args),
    policyVersion: 2,
  })

  await harness.engine.start(session())

  assert.equal(harness.api.policyCalls, 2)
  assert.equal(harness.api.downloadCalls, 0)
  assert.equal(harness.engine.getState().status, 'permission_changed')
})

test('persists each page cursor and carries the terminal resume cursor to the next run', async (t) => {
  const first = entry('r-1', Buffer.from('one'), {
    sourceId: 'doc-1',
    originalName: '一.pdf',
  })
  const second = entry('r-2', Buffer.from('two'), {
    sourceId: 'doc-2',
    originalName: '二.pdf',
  })
  const harness = createTestEngine(t, { manifests: [[first, second], []] })
  const calls = []
  harness.api.getManifest = async (_token, { cursor }) => {
    calls.push(cursor)
    if (cursor === '') {
      return {
        items: [{ ...first, _content: undefined }],
        nextCursor: 'page-2',
        hasMore: true,
        policyVersion: 1,
      }
    }
    if (cursor === 'page-2') {
      return {
        items: [{ ...second, _content: undefined }],
        nextCursor: 'resume-final',
        hasMore: false,
        policyVersion: 1,
      }
    }
    return {
      items: [],
      nextCursor: 'resume-next',
      hasMore: false,
      policyVersion: 1,
    }
  }

  await harness.engine.start(session())
  await harness.engine.start(session())

  assert.deepEqual(calls, ['', 'page-2', 'resume-final'])
  assert.equal(harness.api.downloadCalls, 2)
})
