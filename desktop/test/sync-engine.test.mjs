import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  readdirSync,
  rmSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs'
import {
  mkdir,
  rename as renameFile,
  rm as removeFile,
  writeFile,
} from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import {
  DesktopApiClient,
  SyncApiError,
} from '../src/sync/api-client.mjs'
import { SyncIndexStore } from '../src/sync/index-store.mjs'
import { SyncEngine } from '../src/sync/sync-engine.mjs'

const ORIGIN = 'https://erp.example.cn'
const PROJECT_REF = 'project:p-1'
const OTHER_PROJECT_REF = 'project:p-2'

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

function missingEntry(revision, overrides = {}) {
  return entry(revision, Buffer.alloc(0), {
    availability: 'missing',
    sha256: '',
    downloadPath: null,
    ...overrides,
  })
}

class FakeApiClient {
  constructor({
    manifests,
    policy = {},
    downloadGate = null,
    userId = 'user-1',
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
    this.userId = userId
    this.downloadCalls = 0
    this.manifestCalls = []
    this.policyCalls = 0
    this.activeDownloads = 0
    this.maximumActiveDownloads = 0
    this.run = 0
    this.expectedCursor = ''
    this.aborted = false
    this.contentByPath = new Map()
    for (const manifest of manifests) {
      for (const item of manifest) {
        this.contentByPath.set(item.downloadPath, item._content)
      }
    }
  }

  async getCurrentUser() {
    return {
      id: this.userId,
      username: 'desktop-user',
      displayName: '桌面用户',
      email: '',
      role: 'viewer',
      isActive: true,
      createdAt: '2026-07-27T00:00:00.000Z',
      updatedAt: '2026-07-27T00:00:00.000Z',
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
    if (cursor !== this.expectedCursor) {
      throw new Error(
        `manifest cursor mismatch: expected ${this.expectedCursor}, received ${cursor}`,
      )
    }
    this.manifestCalls.push(cursor)
    const items = this.manifests[Math.min(this.run, this.manifests.length - 1)]
    this.run += 1
    this.expectedCursor = `resume-${this.run}`
    return {
      items: items.map(({ _content, ...item }) => item),
      nextCursor: this.expectedCursor,
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
  const {
    engineOptions = {},
    ...apiOptions
  } = options
  const base = mkdtempSync(join(tmpdir(), 'jiqing-sync-engine-'))
  t.after(() => rmSync(base, { recursive: true, force: true }))
  const localRoot = join(base, 'visible')
  const appDataPath = join(base, 'app-data')
  const api = new FakeApiClient(apiOptions)
  const states = []
  const engine = new SyncEngine({
    apiClient: api,
    appDataPath,
    environmentOrigin: ORIGIN,
    now: () => new Date('2026-07-27T10:05:00.000Z'),
    emitState: (state) => states.push(state),
    ...engineOptions,
  })
  engine.setLocalRoot(localRoot)
  return {
    engine,
    api,
    states,
    localRoot,
    appDataPath,
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

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, reject, resolve }
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
      [],
    ],
  })
  await harness.engine.start(session())
  chmodSync(harness.output('施工合同.pdf'), 0o666)
  unlinkSync(harness.output('施工合同.pdf'))
  assert.equal(existsSync(harness.output('施工合同.pdf')), false)

  await harness.engine.start(session())

  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'contract')
  assert.equal(harness.api.downloadCalls, 2)
  assert.deepEqual(harness.api.manifestCalls, ['', 'resume-1'])
})

test('records a missing manifest source without blocking siblings or cursor advancement', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [
      [
        missingEntry('missing-r1', {
          sourceId: 'missing-doc',
          originalName: '缺失资料.pdf',
        }),
        entry('available-r1', Buffer.from('available'), {
          sourceId: 'available-doc',
          originalName: '可用资料.pdf',
        }),
      ],
      [],
    ],
  })

  await harness.engine.start(session())
  await harness.engine.start(session())

  assert.equal(
    readFileSync(harness.output('可用资料.pdf'), 'utf8'),
    'available',
  )
  assert.equal(harness.api.downloadCalls, 1)
  assert.deepEqual(harness.api.manifestCalls, ['', 'resume-1'])
  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  const index = await store.load()
  assert.equal(index.files['project_file:missing-doc'].status, 'server_missing')
  assert.equal(index.cursorBySelection[PROJECT_REF], 'resume-2')
})

test('restores selected missing files and does not retry unselected failures', async (t) => {
  const content = Buffer.from('selected')
  const harness = createTestEngine(t, {
    manifests: [
      [entry('selected-r1', content)],
      [],
    ],
  })
  await harness.engine.start(session())
  chmodSync(harness.output('施工合同.pdf'), 0o666)
  unlinkSync(harness.output('施工合同.pdf'))

  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  const index = await store.load()
  const unselected = entry('other-r1', Buffer.from('other'), {
    projectRef: OTHER_PROJECT_REF,
    projectCode: '20260727-JQ-002',
    projectName: '未选择项目',
    sourceId: 'other-doc',
  })
  const { _content, ...unselectedItem } = unselected
  index.files['project_file:other-doc'] = {
    ...unselectedItem,
    relativePath: 'other/category/file.pdf',
    physicalFiles: [],
    status: 'failed',
    lastErrorCode: 'download_failed',
    pendingItem: unselectedItem,
  }
  await store.save(index)

  await harness.engine.start(session())

  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'selected')
  assert.equal(harness.api.downloadCalls, 2)
  assert.equal(harness.engine.getState().status, 'completed')
  assert.deepEqual(harness.api.manifestCalls, ['', 'resume-1'])
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

test('real API aborts preserve pause and logout state instead of surfacing offline', async (t) => {
  for (const action of ['pause', 'clearSession']) {
    const base = mkdtempSync(join(tmpdir(), 'jiqing-real-abort-'))
    t.after(() => rmSync(base, { recursive: true, force: true }))
    const localRoot = join(base, 'visible')
    const downloadEntered = deferred()
    const content = Buffer.from('contract')
    const item = entry('r-1', content)
    const fetchImpl = async (url, { signal }) => {
      const path = new URL(url).pathname
      const dataByPath = {
        '/api/auth/me': {
          id: 'user-1',
          isActive: true,
        },
        '/api/desktop/policy': {
          enabled: true,
          enabledForCurrentUser: true,
          maxFileSizeBytes: 1024,
          maxLocalStorageBytes: 1024,
          policyVersion: 1,
        },
        '/api/desktop/sync/projects': [{
          projectRef: PROJECT_REF,
          totalFileSizeBytes: content.length,
        }],
        '/api/desktop/sync/manifest': {
          items: [{ ...item, _content: undefined }],
          nextCursor: 'resume-1',
          hasMore: false,
          policyVersion: 1,
        },
      }
      if (path.includes('/download')) {
        downloadEntered.resolve()
        return new Promise((resolve, reject) => {
          signal.addEventListener('abort', () => reject(signal.reason), {
            once: true,
          })
        })
      }
      return new Response(JSON.stringify({
        success: true,
        data: dataByPath[path],
      }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
    }
    const engine = new SyncEngine({
      apiClient: new DesktopApiClient({
        origin: ORIGIN,
        fetchImpl,
        timeoutMs: 5_000,
      }),
      appDataPath: join(base, 'app-data'),
      environmentOrigin: ORIGIN,
    })
    engine.setLocalRoot(localRoot)

    const running = engine.start(session())
    await downloadEntered.promise
    engine[action]()

    await assert.doesNotReject(running)
    assert.equal(engine.getState().status, 'paused')
    assert.equal(engine.hasActiveSession(), false)
    assert.equal(existsSync(join(localRoot, '施工合同.pdf')), false)
  }
})

test('pause during an awaited part hash prevents file and cursor publication', async (t) => {
  const hashEntered = deferred()
  const releaseHash = deferred()
  let held = false
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
    engineOptions: {
      async hashFile(path) {
        if (path.includes('.jiqing-part-') && !held) {
          held = true
          hashEntered.resolve()
          await releaseHash.promise
        }
        return digest(readFileSync(path))
      },
    },
  })

  const running = harness.engine.start(session())
  const boundary = await Promise.race([
    hashEntered.promise.then(() => 'hash'),
    running.then(() => 'completed'),
  ])
  assert.equal(boundary, 'hash')
  harness.engine.pause()
  releaseHash.resolve()
  await running

  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
  assert.equal(harness.engine.getState().status, 'paused')
  const indexDirectory = join(harness.localRoot, '..', 'app-data', 'sync-index')
  const indexFiles = existsSync(indexDirectory)
    ? readdirSync(indexDirectory, { recursive: true })
    : []
  assert.equal(indexFiles.some((name) => String(name).endsWith('.tmp')), false)
})

test('pause during an awaited index save rolls back file and cursor publication', async (t) => {
  const saveEntered = deferred()
  const releaseSave = deferred()
  let held = false
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
    engineOptions: {
      indexStoreFactory(userId) {
        const store = new SyncIndexStore({
          appDataPath: join(harness.localRoot, '..', 'app-data'),
          environmentOrigin: ORIGIN,
          userId,
        })
        return {
          load: () => store.load(),
          async save(index, options) {
            if (Object.keys(index.files).length > 0 && !held) {
              held = true
              saveEntered.resolve()
              await releaseSave.promise
            }
            return store.save(index, options)
          },
        }
      },
    },
  })

  const running = harness.engine.start(session())
  const boundary = await Promise.race([
    saveEntered.promise.then(() => 'save'),
    running.then(() => 'completed'),
  ])
  assert.equal(boundary, 'save')
  harness.engine.pause()
  releaseSave.resolve()
  await running

  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
  assert.equal(harness.engine.getState().status, 'paused')
  const indexFiles = readdirSync(
    join(harness.localRoot, '..', 'app-data', 'sync-index'),
    { recursive: true },
  )
  assert.equal(indexFiles.some((name) => String(name).includes('.tmp-')), false)
})

test('pause after an awaited index commit restores the persisted baseline', async (t) => {
  const commitFinished = deferred()
  const releaseSave = deferred()
  let held = false
  let capturedStore
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
    engineOptions: {
      indexStoreFactory(userId) {
        capturedStore = new SyncIndexStore({
          appDataPath: join(harness.localRoot, '..', 'app-data'),
          environmentOrigin: ORIGIN,
          userId,
        })
        return {
          load: () => capturedStore.load(),
          async save(index, options) {
            await capturedStore.save(index, options)
            if (Object.keys(index.files).length > 0 && !held) {
              held = true
              commitFinished.resolve()
              await releaseSave.promise
            }
          },
        }
      },
    },
  })

  const running = harness.engine.start(session())
  const boundary = await Promise.race([
    commitFinished.promise.then(() => 'commit'),
    running.then(() => 'completed'),
  ])
  assert.equal(boundary, 'commit')
  harness.engine.pause()
  releaseSave.resolve()
  await running

  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
  const persisted = await capturedStore.load()
  assert.deepEqual(persisted.files, {})
  assert.deepEqual(persisted.cursorBySelection, {})
})

test('a same-user replacement run waits for cancellation and publishes only its revision', async (t) => {
  const hashEntered = deferred()
  const releaseHash = deferred()
  let held = false
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('server-v1'))],
      [entry('r-2', Buffer.from('server-v2'))],
    ],
    engineOptions: {
      async hashFile(path) {
        if (path.includes('.jiqing-part-') && !held) {
          held = true
          hashEntered.resolve()
          await releaseHash.promise
        }
        return digest(readFileSync(path))
      },
    },
  })
  let snapshot = 0
  harness.api.getManifest = async (_token, { cursor }) => {
    assert.equal(cursor, '')
    harness.api.manifestCalls.push(cursor)
    const items = harness.api.manifests[snapshot++]
    return {
      items: items.map(({ _content, ...item }) => item),
      nextCursor: `replacement-${snapshot}`,
      hasMore: false,
      policyVersion: 1,
    }
  }

  const first = harness.engine.start(session())
  const boundary = await Promise.race([
    hashEntered.promise.then(() => 'hash'),
    first.then(() => 'completed'),
  ])
  assert.equal(boundary, 'hash')
  const second = harness.engine.start(session())
  releaseHash.resolve()
  await Promise.all([first, second])

  assert.equal(
    readFileSync(harness.output('施工合同.pdf'), 'utf8'),
    'server-v2',
  )
  assert.equal(
    readdirSync(join(harness.output('施工合同.pdf'), '..'))
      .some((name) => name.startsWith('.jiqing-part-')),
    false,
  )
})

test('a root replacement waits for the prior user index transaction to unwind', async (t) => {
  const saveEntered = deferred()
  const releaseSave = deferred()
  let held = false
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('root-one'))],
      [entry('r-2', Buffer.from('root-two'))],
    ],
    engineOptions: {
      indexStoreFactory(userId) {
        const store = new SyncIndexStore({
          appDataPath: harness.appDataPath,
          environmentOrigin: ORIGIN,
          userId,
        })
        return {
          load: () => store.load(),
          async save(index, options) {
            if (Object.keys(index.files).length > 0 && !held) {
              held = true
              saveEntered.resolve()
              await releaseSave.promise
            }
            return store.save(index, options)
          },
        }
      },
    },
  })
  let snapshot = 0
  harness.api.getManifest = async (_token, { cursor }) => {
    assert.equal(cursor, '')
    harness.api.manifestCalls.push(cursor)
    const items = harness.api.manifests[snapshot++]
    return {
      items: items.map(({ _content, ...item }) => item),
      nextCursor: `root-replacement-${snapshot}`,
      hasMore: false,
      policyVersion: 1,
    }
  }
  const secondRoot = join(harness.localRoot, '..', 'visible-two')

  const first = harness.engine.start(session())
  await saveEntered.promise
  harness.engine.setLocalRoot(secondRoot)
  const second = harness.engine.start(session())

  const ordering = await Promise.race([
    second.then(() => 'completed'),
    new Promise((resolve) => setTimeout(() => resolve('waiting'), 30)),
  ])
  assert.equal(ordering, 'waiting')
  assert.equal(harness.api.policyCalls, 1)

  releaseSave.resolve()
  await Promise.all([first, second])

  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
  assert.equal(
    readFileSync(join(
      secondRoot,
      '20260727-JQ-001_区直学校维修',
      '合同文件',
      '施工合同.pdf',
    ), 'utf8'),
    'root-two',
  )
})

test('workers with colliding names and sanitized source ids publish distinct verified files', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[
      entry('r-1', Buffer.from('first'), {
        sourceId: 'doc:1',
        originalName: '合同?.pdf',
      }),
      entry('r-2', Buffer.from('second'), {
        sourceId: 'doc?1',
        originalName: '合同*.pdf',
      }),
    ]],
    downloadGate: () => new Promise((resolve) => setTimeout(resolve, 5)),
  })

  await harness.engine.start(session())

  const directory = join(
    harness.localRoot,
    '20260727-JQ-001_区直学校维修',
    '合同文件',
  )
  const files = readdirSync(directory)
  assert.equal(files.some((name) => name.startsWith('.jiqing-part-')), false)
  assert.deepEqual(
    files.map((name) => readFileSync(join(directory, name), 'utf8')).sort(),
    ['first', 'second'],
  )
})

test('a failed server update preserves the trusted baseline for the next retry', async (t) => {
  const v1 = Buffer.from('server-v1')
  const v2 = Buffer.from('server-v2')
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', v1)],
      [entry('r-2', v2, { sha256: '0'.repeat(64) })],
      [entry('r-2', v2)],
    ],
  })
  await harness.engine.start(session())
  await harness.engine.start(session())

  await harness.engine.start(session())

  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'server-v2')
  assert.equal(existsSync(harness.output('施工合同_服务器新版.pdf')), false)
})

test('pause during trusted-backup cleanup keeps the committed replacement', async (t) => {
  const cleanupEntered = deferred()
  const releaseCleanup = deferred()
  let held = false
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('server-v1'))],
      [entry('r-2', Buffer.from('server-v2'))],
    ],
    engineOptions: {
      async removeFile(path, options) {
        if (path.includes('.jiqing-backup-') && !held) {
          held = true
          cleanupEntered.resolve()
          await releaseCleanup.promise
        }
        return removeFile(path, options)
      },
    },
  })
  await harness.engine.start(session())

  const updating = harness.engine.start(session())
  const boundary = await Promise.race([
    cleanupEntered.promise.then(() => 'cleanup'),
    updating.then(() => 'completed'),
  ])
  assert.equal(boundary, 'cleanup')
  harness.engine.pause()
  releaseCleanup.resolve()
  await updating

  assert.equal(harness.engine.getState().status, 'paused')
  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'server-v2')
  assert.equal(
    readdirSync(harness.localRoot, { recursive: true })
      .some((name) => String(name).includes('.jiqing-backup-')),
    false,
  )
  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  assert.equal(
    (await store.load()).files['project_file:doc-1'].sourceRevision,
    'r-2',
  )
})

test('root replacement after cleanup failure still persists recovery tracking', async (t) => {
  const cleanupEntered = deferred()
  const releaseCleanup = deferred()
  let held = false
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('server-v1'))],
      [entry('r-2', Buffer.from('server-v2'))],
    ],
    engineOptions: {
      async removeFile(path, options) {
        if (path.includes('.jiqing-backup-') && !held) {
          held = true
          cleanupEntered.resolve()
          await releaseCleanup.promise
          throw new Error('backup cleanup denied')
        }
        return removeFile(path, options)
      },
    },
  })
  await harness.engine.start(session())

  const updating = harness.engine.start(session())
  const boundary = await Promise.race([
    cleanupEntered.promise.then(() => 'cleanup'),
    updating.then(() => 'completed'),
  ])
  assert.equal(boundary, 'cleanup')
  const replacementRoot = join(harness.localRoot, '..', 'replacement-root')
  harness.engine.setLocalRoot(replacementRoot)
  releaseCleanup.resolve()
  await updating

  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  const index = await store.load()
  const recoveryEntries = Object.values(index.recoveryEntries)
  assert.equal(harness.engine.getState().status, 'paused')
  assert.equal(harness.engine.getState().localRoot, replacementRoot)
  assert.equal(recoveryEntries.length, 1)
  assert.equal(recoveryEntries[0].rootPath, realpathSync(harness.localRoot))
  assert.equal(
    readFileSync(
      join(harness.localRoot, recoveryEntries[0].physicalFiles[0]),
      'utf8',
    ),
    'server-v1',
  )
})

test('failed replacement rollback preserves both copies and records an explicit failure', async (t) => {
  let failUpdateSave = true
  let failRestore = true
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('server-v1'))],
      [entry('r-2', Buffer.from('server-v2'))],
    ],
    engineOptions: {
      indexStoreFactory(userId) {
        const store = new SyncIndexStore({
          appDataPath: harness.appDataPath,
          environmentOrigin: ORIGIN,
          userId,
        })
        return {
          load: () => store.load(),
          save(index, options) {
            const record = index.files['project_file:doc-1']
            if (record?.sourceRevision === 'r-2' && failUpdateSave) {
              failUpdateSave = false
              throw new Error('index commit denied')
            }
            return store.save(index, options)
          },
        }
      },
      async renameFile(source, destination) {
        if (source.includes('.jiqing-backup-') && failRestore) {
          failRestore = false
          throw new Error('trusted backup restore denied')
        }
        return renameFile(source, destination)
      },
    },
  })
  await harness.engine.start(session())

  await harness.engine.start(session())

  assert.equal(harness.engine.getState().status, 'partial_failure')
  const files = readdirSync(harness.localRoot, { recursive: true })
    .map(String)
  assert.equal(files.some((name) => name.includes('.jiqing-backup-')), true)
  assert.equal(files.some((name) => name.includes('.jiqing-rollback-')), true)
  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  assert.equal(
    (await store.load()).files['project_file:doc-1'].lastErrorCode,
    'publication_rollback_failed',
  )
})

test('index rollback failure preserves both revisions in quota-accounted recovery paths', async (t) => {
  let publicationSaveFailed = false
  let rollbackSaveFailed = false
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('old-1'))],
      [entry('r-2', Buffer.from('new-2'))],
      [entry('r-3', Buffer.from('extra'), {
        sourceId: 'doc-2',
        originalName: '追加资料.pdf',
      })],
    ],
    policy: {
      maxFileSizeBytes: 5,
      maxLocalStorageBytes: 10,
    },
    engineOptions: {
      indexStoreFactory(userId) {
        const store = new SyncIndexStore({
          appDataPath: harness.appDataPath,
          environmentOrigin: ORIGIN,
          userId,
        })
        return {
          load: () => store.load(),
          save(index, options) {
            const record = index.files['project_file:doc-1']
            if (record?.sourceRevision === 'r-2' && !publicationSaveFailed) {
              publicationSaveFailed = true
              throw new Error('publication index save denied')
            }
            if (record?.sourceRevision === 'r-1'
              && Object.keys(index.recoveryEntries ?? {}).length > 0
              && !rollbackSaveFailed) {
              rollbackSaveFailed = true
              throw new Error('rollback index save denied')
            }
            return store.save(index, options)
          },
        }
      },
      async removeFile(path, options) {
        if (path.includes('.jiqing-rollback-')) {
          throw new Error('defer recovery cleanup')
        }
        return removeFile(path, options)
      },
    },
  })
  await harness.engine.start(session())

  await harness.engine.start(session())

  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'old-1')
  const recoveryFiles = readdirSync(harness.localRoot, { recursive: true })
    .map(String)
    .filter((name) => name.includes('.jiqing-rollback-'))
  assert.equal(recoveryFiles.length, 1)
  assert.equal(
    readFileSync(join(harness.localRoot, recoveryFiles[0]), 'utf8'),
    'new-2',
  )
  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  const recoveredIndex = await store.load()
  const recoveryEntries = Object.values(recoveredIndex.recoveryEntries ?? {})
  assert.equal(recoveryEntries.length, 1)
  assert.equal(recoveryEntries[0].physicalFiles[0], recoveryFiles[0])
  assert.equal(recoveryEntries[0].accountedBytes, 5)

  recoveredIndex.files['project_file:doc-1'] = {
    ...recoveredIndex.files['project_file:doc-1'],
    status: 'synced',
    lastErrorCode: null,
    pendingItem: null,
  }
  await store.save(recoveredIndex)
  await harness.engine.start(session())

  assert.equal(existsSync(harness.output('追加资料.pdf')), false)
  assert.equal(harness.engine.getState().status, 'partial_failure')
})

test('pause after index rollback failure still persists recovery tracking', async (t) => {
  const rollbackSaveEntered = deferred()
  const releaseRollbackSave = deferred()
  let publicationSaveFailed = false
  let rollbackSaveFailed = false
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('old-1'))],
      [entry('r-2', Buffer.from('new-2'))],
    ],
    engineOptions: {
      indexStoreFactory(userId) {
        const store = new SyncIndexStore({
          appDataPath: harness.appDataPath,
          environmentOrigin: ORIGIN,
          userId,
        })
        return {
          load: () => store.load(),
          async save(index, options) {
            const record = index.files['project_file:doc-1']
            if (record?.sourceRevision === 'r-2' && !publicationSaveFailed) {
              publicationSaveFailed = true
              throw new Error('publication index save denied')
            }
            if (record?.sourceRevision === 'r-1'
              && Object.keys(index.recoveryEntries ?? {}).length > 0
              && !rollbackSaveFailed) {
              rollbackSaveFailed = true
              rollbackSaveEntered.resolve()
              await releaseRollbackSave.promise
              throw new Error('rollback index save denied')
            }
            return store.save(index, options)
          },
        }
      },
    },
  })
  await harness.engine.start(session())

  const updating = harness.engine.start(session())
  const boundary = await Promise.race([
    rollbackSaveEntered.promise.then(() => 'rollback-save'),
    updating.then(() => 'completed'),
  ])
  assert.equal(boundary, 'rollback-save')
  harness.engine.pause()
  releaseRollbackSave.resolve()
  await updating

  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  const index = await store.load()
  const recoveryEntries = Object.values(index.recoveryEntries)
  assert.equal(harness.engine.getState().status, 'paused')
  assert.equal(recoveryEntries.length, 1)
  assert.equal(recoveryEntries[0].rootPath, realpathSync(harness.localRoot))
  assert.equal(
    readFileSync(
      join(harness.localRoot, recoveryEntries[0].physicalFiles[0]),
      'utf8',
    ),
    'new-2',
  )
  assert.equal(
    readFileSync(
      join(
        harness.localRoot,
        index.files['project_file:doc-1'].relativePath,
      ),
      'utf8',
    ),
    'old-1',
  )
})

test('cleanup-pending backups stay quota-accounted until a later explicit cleanup succeeds', async (t) => {
  let cleanupAttempts = 0
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('old-1'))],
      [entry('r-2', Buffer.from('new-2'))],
      [entry('r-3', Buffer.from('extra'), {
        sourceId: 'doc-2',
        originalName: '追加资料.pdf',
      })],
      [],
    ],
    policy: {
      maxFileSizeBytes: 5,
      maxLocalStorageBytes: 10,
    },
    engineOptions: {
      async removeFile(path, options) {
        if (path.includes('.jiqing-backup-')) {
          cleanupAttempts += 1
          if (cleanupAttempts <= 2) {
            throw new Error('backup cleanup denied')
          }
        }
        return removeFile(path, options)
      },
    },
  })
  await harness.engine.start(session())
  await harness.engine.start(session())

  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  let index = await store.load()
  assert.equal(Object.keys(index.recoveryEntries ?? {}).length, 1)
  assert.equal(
    readdirSync(harness.localRoot, { recursive: true })
      .map(String)
      .some((name) => name.includes('.jiqing-backup-')),
    true,
  )

  await harness.engine.start(session())

  assert.equal(cleanupAttempts, 2)
  assert.equal(existsSync(harness.output('追加资料.pdf')), false)
  index = await store.load()
  assert.equal(Object.keys(index.recoveryEntries ?? {}).length, 1)

  await harness.engine.start(session())

  assert.equal(cleanupAttempts, 3)
  assert.equal(readFileSync(harness.output('追加资料.pdf'), 'utf8'), 'extra')
  index = await store.load()
  assert.deepEqual(index.recoveryEntries, {})
  assert.equal(
    readdirSync(harness.localRoot, { recursive: true })
      .map(String)
      .some((name) => name.includes('.jiqing-backup-')),
    false,
  )
})

test('root change keeps recovery cleanup and quota bound to the artifact root', async (t) => {
  const cleanupPaths = []
  let rootA
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('old-1'))],
      [entry('r-2', Buffer.from('new-2'))],
      [entry('r-3', Buffer.from('sixsix'), {
        sourceId: 'doc-2',
        originalName: '杩藉姞璧勬枡.pdf',
      })],
    ],
    policy: {
      maxFileSizeBytes: 6,
      maxLocalStorageBytes: 10,
    },
    engineOptions: {
      async removeFile(path, options) {
        if (path.includes('.jiqing-backup-')) {
          cleanupPaths.push(path)
          if (rootA && path.startsWith(rootA)) {
            throw new Error('root A cleanup deferred')
          }
        }
        return removeFile(path, options)
      },
    },
  })
  mkdirSync(harness.localRoot, { recursive: true })
  rootA = realpathSync(harness.localRoot)
  await harness.engine.start(session())
  await harness.engine.start(session())

  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  let index = await store.load()
  const [recovery] = Object.values(index.recoveryEntries)
  assert.equal(recovery.rootPath, rootA)
  const rootAArtifact = join(rootA, recovery.physicalFiles[0])
  assert.equal(readFileSync(rootAArtifact, 'utf8'), 'old-1')

  const rootB = join(harness.localRoot, '..', 'visible-b')
  mkdirSync(rootB, { recursive: true })
  const rootBSentinel = join(rootB, recovery.physicalFiles[0])
  writeFileSync(rootBSentinel, 'keep-root-b', 'utf8')
  harness.engine.setLocalRoot(rootB)
  await harness.engine.start(session())

  index = await store.load()
  assert.equal(readFileSync(rootAArtifact, 'utf8'), 'old-1')
  assert.equal(readFileSync(rootBSentinel, 'utf8'), 'keep-root-b')
  assert.equal(Object.keys(index.recoveryEntries).length, 1)
  assert.ok(cleanupPaths.length >= 2)
  assert.equal(
    cleanupPaths.slice(1).every((path) => path.startsWith(rootA)),
    true,
  )
  assert.equal(
    index.files['project_file:doc-2'].lastErrorCode,
    'policy_storage_limit',
  )
  assert.equal(index.files['project_file:doc-2'].relativePath, null)
})

test('malformed recovery ledger never deletes a selected-root file', async (t) => {
  const harness = createTestEngine(t, { manifests: [[]] })
  mkdirSync(harness.localRoot, { recursive: true })
  const sentinel = join(harness.localRoot, 'keep.txt')
  writeFileSync(sentinel, 'keep-me', 'utf8')
  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  const index = await store.load()
  const transactionId = 'a'.repeat(32)
  index.recoveryEntries[transactionId] = {
    id: transactionId,
    sourceKey: 'project_file:doc-1',
    type: 'cleanup_pending',
    rootPath: realpathSync(harness.localRoot),
    physicalFiles: ['keep.txt'],
    cleanupFiles: ['keep.txt'],
    accountedBytes: 7,
    createdAt: '2026-07-27T10:05:00.000Z',
  }
  await store.save(await store.load())
  writeFileSync(store.filePath, JSON.stringify(index), 'utf8')

  await harness.engine.start(session())

  assert.equal(readFileSync(sentinel, 'utf8'), 'keep-me')
  assert.equal(
    readdirSync(store.directoryPath)
      .some((name) => name.includes('.corrupt-')),
    true,
  )
})

test('failed first publication moves bytes to a tracked recovery path', async (t) => {
  let failIndexSave = true
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('server-v1'))]],
    engineOptions: {
      indexStoreFactory(userId) {
        const store = new SyncIndexStore({
          appDataPath: harness.appDataPath,
          environmentOrigin: ORIGIN,
          userId,
        })
        return {
          load: () => store.load(),
          save(index, options) {
            if (Object.keys(index.files).length > 0 && failIndexSave) {
              failIndexSave = false
              throw new Error('index commit denied')
            }
            return store.save(index, options)
          },
        }
      },
      async removeFile(path, options) {
        if (path.includes('.jiqing-rollback-')) {
          throw new Error('rollback cleanup denied')
        }
        return removeFile(path, options)
      },
    },
  })

  await harness.engine.start(session())

  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
  const files = readdirSync(harness.localRoot, { recursive: true }).map(String)
  assert.equal(files.some((name) => name.includes('.jiqing-rollback-')), true)
  const store = new SyncIndexStore({
    appDataPath: harness.appDataPath,
    environmentOrigin: ORIGIN,
    userId: 'user-1',
  })
  assert.equal(
    (await store.load()).files['project_file:doc-1'].lastErrorCode,
    'download_failed',
  )
  assert.equal(
    Object.keys((await store.load()).recoveryEntries).length,
    1,
  )
})

test('quota is recalculated when a local file changes during download', async (t) => {
  const releaseDownload = deferred()
  let downloads = 0
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('12345'))],
      [entry('r-2', Buffer.from('123456'))],
    ],
    policy: {
      maxLocalStorageBytes: 10,
    },
    downloadGate: async () => {
      downloads += 1
      if (downloads === 2) await releaseDownload.promise
    },
  })
  await harness.engine.start(session())
  chmodSync(harness.output('施工合同.pdf'), 0o666)

  const updating = harness.engine.start(session())
  while (harness.api.activeDownloads === 0) {
    await new Promise((resolve) => setTimeout(resolve, 1))
  }
  writeFileSync(harness.output('施工合同.pdf'), 'local-123')
  releaseDownload.resolve()
  await updating

  assert.equal(readFileSync(harness.output('施工合同.pdf'), 'utf8'), 'local-123')
  assert.equal(existsSync(harness.output('施工合同_服务器新版.pdf')), false)
  assert.equal(harness.engine.getState().status, 'partial_failure')
})

test('quota includes older indexed conflict files', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [
      [entry('r-1', Buffer.from('12345'))],
      [entry('r-2', Buffer.from('123456'))],
      [entry('r-3', Buffer.from('1234567'))],
    ],
    policy: {
      maxLocalStorageBytes: 11,
    },
  })
  await harness.engine.start(session())
  chmodSync(harness.output('施工合同.pdf'), 0o666)
  writeFileSync(harness.output('施工合同.pdf'), 'local')
  await harness.engine.start(session())

  await harness.engine.start(session())

  assert.equal(
    readFileSync(harness.output('施工合同_服务器新版.pdf'), 'utf8'),
    '123456',
  )
  assert.equal(harness.engine.getState().status, 'partial_failure')
})

test('concurrent new files exactly filling quota both publish', async (t) => {
  const bothDownloadsEntered = deferred()
  const releaseDownloads = deferred()
  let downloadsEntered = 0
  const harness = createTestEngine(t, {
    manifests: [[
      entry('r-1', Buffer.from('12345'), {
        sourceId: 'doc-1',
        originalName: '一.pdf',
      }),
      entry('r-2', Buffer.from('67890'), {
        sourceId: 'doc-2',
        originalName: '二.pdf',
      }),
    ]],
    policy: {
      maxFileSizeBytes: 5,
      maxLocalStorageBytes: 10,
    },
    downloadGate: async () => {
      downloadsEntered += 1
      if (downloadsEntered === 2) bothDownloadsEntered.resolve()
      await releaseDownloads.promise
    },
  })

  const running = harness.engine.start(session())
  const boundary = await Promise.race([
    bothDownloadsEntered.promise.then(() => 'both-downloads'),
    running.then(() => 'completed'),
  ])
  assert.equal(boundary, 'both-downloads')
  assert.equal(harness.api.activeDownloads, 2)
  releaseDownloads.resolve()
  await running

  assert.equal(harness.engine.getState().completedFiles, 2)
  assert.equal(harness.engine.getState().failedFiles, 0)
  assert.equal(harness.engine.getState().status, 'completed')
})

test('read-only preparation failure leaves no visible or indexed file', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
    engineOptions: {
      async prepareReadOnly() {
        throw new Error('chmod denied')
      },
    },
  })

  await harness.engine.start(session())

  assert.equal(existsSync(harness.output('施工合同.pdf')), false)
  assert.equal(harness.engine.getState().status, 'partial_failure')
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

test('binds the renderer session user to the authenticated server identity', async (t) => {
  const harness = createTestEngine(t, {
    manifests: [[entry('r-1', Buffer.from('contract'))]],
  })

  await harness.engine.start({
    ...session(),
    userId: 'renderer-spoof',
  })

  assert.equal(harness.api.downloadCalls, 0)
  assert.equal(harness.engine.getState().status, 'permission_changed')
})

test('rejects missing or inactive authenticated server identities', async (t) => {
  for (const identity of [
    {},
    { id: 'user-1', isActive: false },
  ]) {
    const harness = createTestEngine(t, {
      manifests: [[entry('r-1', Buffer.from('contract'))]],
    })
    harness.api.getCurrentUser = async () => identity

    await harness.engine.start(session())

    assert.equal(harness.api.downloadCalls, 0)
    assert.equal(harness.engine.getState().status, 'permission_changed')
  }
})

test('clears the run token when the initial state emission throws', async (t) => {
  const base = mkdtempSync(join(tmpdir(), 'jiqing-sync-engine-'))
  t.after(() => rmSync(base, { recursive: true, force: true }))
  const api = new FakeApiClient({ manifests: [[]] })
  const engine = new SyncEngine({
    apiClient: api,
    appDataPath: join(base, 'app-data'),
    environmentOrigin: ORIGIN,
    emitState(state) {
      if (state.status === 'checking_policy') throw new Error('renderer gone')
    },
  })
  engine.setLocalRoot(join(base, 'visible'))

  await assert.rejects(engine.start(session()), /renderer gone/)

  assert.equal(engine.hasActiveSession(), false)
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

test('fails closed on malformed manifest page shapes', async (t) => {
  for (const malformed of [
    null,
    {},
    { items: {}, nextCursor: 'resume', hasMore: false, policyVersion: 1 },
    { items: [], nextCursor: '', hasMore: false, policyVersion: 1 },
    { items: [], nextCursor: 'resume', hasMore: 'false', policyVersion: 1 },
    { items: [], nextCursor: 'resume', hasMore: false, policyVersion: 0 },
    {
      items: [{
        ...entry('r-1', Buffer.from('contract')),
        _content: undefined,
        sha256: 'not-a-sha256',
      }],
      nextCursor: 'resume',
      hasMore: false,
      policyVersion: 1,
    },
  ]) {
    const harness = createTestEngine(t, { manifests: [[]] })
    harness.api.getManifest = async () => malformed

    await harness.engine.start(session())

    assert.equal(harness.api.downloadCalls, 0)
    assert.equal(harness.engine.getState().status, 'partial_failure')
  }
})

test('rejects missing and repeated pagination cursors without looping', async (t) => {
  for (const nextCursors of [
    [''],
    ['page-2', 'page-2'],
  ]) {
    const harness = createTestEngine(t, { manifests: [[]] })
    let calls = 0
    harness.api.getManifest = async () => {
      const nextCursor = nextCursors[Math.min(calls, nextCursors.length - 1)]
      calls += 1
      if (calls > 3) throw new Error('manifest loop')
      return {
        items: [],
        nextCursor,
        hasMore: true,
        policyVersion: 1,
      }
    }

    await harness.engine.start(session())

    assert.equal(calls, nextCursors.length)
    assert.equal(harness.engine.getState().status, 'partial_failure')
  }
})
