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
import { SyncIndexStore } from '../src/sync/index-store.mjs'
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
