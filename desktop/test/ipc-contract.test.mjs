import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DESKTOP_IPC_CHANNELS,
  createDesktopIpcController,
  registerDesktopIpcHandlers,
  validateSyncStartRequest,
} from '../src/ipc-contract.mjs'

const TRUSTED_ORIGIN = 'https://erp.example.cn'

function validStartRequest(overrides = {}) {
  return {
    authToken: 'session-token',
    userId: 'user-1',
    projectRefs: ['project:p-1', 'audit:a-2'],
    ...overrides,
  }
}

test('desktop IPC contract contains exactly six requests and one state event', () => {
  assert.deepEqual(DESKTOP_IPC_CHANNELS, {
    getCapabilities: 'desktop:get-capabilities',
    selectSyncFolder: 'desktop:select-sync-folder',
    getSyncState: 'desktop:get-sync-state',
    startSync: 'desktop:start-sync',
    pauseSync: 'desktop:pause-sync',
    openSyncFolder: 'desktop:open-sync-folder',
    syncState: 'desktop:sync-state',
  })
})

test('sync start request accepts a bounded exact request', () => {
  assert.deepEqual(
    validateSyncStartRequest(validStartRequest()),
    validStartRequest(),
  )
})

test('sync start request rejects malformed and extra values', () => {
  for (const request of [
    null,
    [],
    validStartRequest({ extra: true }),
    validStartRequest({ authToken: '' }),
    validStartRequest({ authToken: 'x'.repeat(8193) }),
    validStartRequest({ userId: '' }),
    validStartRequest({ userId: 'x'.repeat(129) }),
    validStartRequest({ projectRefs: 'project:p-1' }),
    validStartRequest({ projectRefs: ['project:p-1', 'project:p-1'] }),
    validStartRequest({ projectRefs: ['project:unsafe/value'] }),
    validStartRequest({
      projectRefs: Array.from(
        { length: 501 },
        (_, index) => `project:p-${index}`,
      ),
    }),
  ]) {
    assert.throws(() => validateSyncStartRequest(request), /invalid/i)
  }
})

test('controller stores token only in a private session and pause clears it', () => {
  const controller = createDesktopIpcController()
  const state = controller.start(validStartRequest())

  assert.equal(state.status, 'checking_policy')
  assert.equal(state.completedFiles, 0)
  assert.equal(state.totalFiles, 0)
  assert.equal(JSON.stringify(state).includes('session-token'), false)
  assert.equal(controller.hasActiveSession(), true)

  const paused = controller.pause()
  assert.equal(paused.status, 'paused')
  assert.equal(controller.hasActiveSession(), false)
})

test('controller never reports fabricated synchronization success', () => {
  const controller = createDesktopIpcController()
  controller.start(validStartRequest())

  const state = controller.getState()
  assert.notEqual(state.status, 'completed')
  assert.equal(state.bytesDownloaded, 0)
  assert.equal(state.lastSuccessAt, '')
  assert.match(state.message, /未下载/)
})

test('logout-equivalent session clear removes project scope but keeps local root', () => {
  const controller = createDesktopIpcController()
  controller.setLocalRoot('C:\\ERP Files')
  controller.start(validStartRequest())

  controller.clearSession()
  const state = controller.getState()
  assert.equal(controller.hasActiveSession(), false)
  assert.equal(state.status, 'paused')
  assert.equal(state.localRoot, 'C:\\ERP Files')
  assert.deepEqual(state.selectedProjectRefs, [])
})

test('controller delegates validated sessions and folder state to one sync engine', async () => {
  const calls = []
  const completed = {
    status: 'completed',
    localRoot: 'C:\\ERP Files',
    selectedProjectRefs: ['project:p-1', 'audit:a-2'],
    completedFiles: 1,
    totalFiles: 1,
    failedFiles: 0,
    bytesDownloaded: 8,
    lastSuccessAt: '2026-07-27T10:05:00.000Z',
    message: '服务器资料已同步到本地',
  }
  const engine = {
    getState: () => completed,
    hasActiveSession: () => false,
    setLocalRoot(path) {
      calls.push(['root', path])
      return { ...completed, localRoot: path }
    },
    async start(request) {
      calls.push(['start', request])
      return completed
    },
    pause() {
      calls.push(['pause'])
      return { ...completed, status: 'paused' }
    },
    clearSession() {
      calls.push(['clear'])
    },
  }
  const controller = createDesktopIpcController({ syncEngine: engine })

  controller.setLocalRoot('C:\\ERP Files')
  assert.deepEqual(await controller.start(validStartRequest()), completed)
  controller.pause()
  controller.clearSession()

  assert.deepEqual(calls, [
    ['root', 'C:\\ERP Files'],
    ['start', validStartRequest()],
    ['pause'],
    ['clear'],
  ])
})

function createIpcHarness() {
  const handlers = new Map()
  return {
    handlers,
    ipcMain: {
      handle(channel, handler) {
        handlers.set(channel, handler)
      },
    },
  }
}

test('every request handler rejects an untrusted sender before side effects', async () => {
  const harness = createIpcHarness()
  let selected = 0
  let opened = 0
  registerDesktopIpcHandlers({
    ipcMain: harness.ipcMain,
    allowedOrigin: TRUSTED_ORIGIN,
    appVersion: '1.2.3',
    releaseChannel: 'internal-test',
    controller: createDesktopIpcController(),
    async selectFolder() {
      selected += 1
      return 'C:\\Authorized'
    },
    async openFolder() {
      opened += 1
    },
  })

  assert.equal(harness.handlers.size, 6)
  for (const [channel, handler] of harness.handlers) {
    const args = channel === DESKTOP_IPC_CHANNELS.startSync
      ? [validStartRequest()]
      : []
    await assert.rejects(
      handler({ senderFrame: { url: 'https://evil.example/' } }, ...args),
      /untrusted ipc sender/,
      channel,
    )
  }
  assert.equal(selected, 0)
  assert.equal(opened, 0)
})

test('trusted handlers reject unexpected arguments and expose real capability metadata', async () => {
  const harness = createIpcHarness()
  registerDesktopIpcHandlers({
    ipcMain: harness.ipcMain,
    allowedOrigin: TRUSTED_ORIGIN,
    appVersion: '2.4.6',
    releaseChannel: 'production',
    controller: createDesktopIpcController(),
    async selectFolder() {
      return ''
    },
    async openFolder() {},
  })
  const event = { senderFrame: { url: `${TRUSTED_ORIGIN}/#/materials` } }

  assert.deepEqual(
    await harness.handlers.get(DESKTOP_IPC_CHANNELS.getCapabilities)(event),
    {
      desktop: true,
      protocolVersion: 1,
      clientVersion: '2.4.6',
      releaseChannel: 'production',
    },
  )
  await assert.rejects(
    harness.handlers.get(DESKTOP_IPC_CHANNELS.getSyncState)(event, 'extra'),
    /unexpected/i,
  )
})

test('folder handlers use only the selected in-memory root', async () => {
  const harness = createIpcHarness()
  const opened = []
  const controller = createDesktopIpcController()
  registerDesktopIpcHandlers({
    ipcMain: harness.ipcMain,
    allowedOrigin: TRUSTED_ORIGIN,
    appVersion: '1.0.0',
    releaseChannel: 'development',
    controller,
    async selectFolder() {
      return 'C:\\ERP Files'
    },
    async openFolder(path) {
      opened.push(path)
    },
  })
  const event = { senderFrame: { url: `${TRUSTED_ORIGIN}/#/materials` } }

  await assert.rejects(
    harness.handlers.get(DESKTOP_IPC_CHANNELS.openSyncFolder)(event),
    /not selected/i,
  )
  assert.equal(
    await harness.handlers.get(DESKTOP_IPC_CHANNELS.selectSyncFolder)(event),
    'C:\\ERP Files',
  )
  await harness.handlers.get(DESKTOP_IPC_CHANNELS.openSyncFolder)(event)
  assert.deepEqual(opened, ['C:\\ERP Files'])
})

test('async synchronization emits only the resolved serializable state', async () => {
  const harness = createIpcHarness()
  const emitted = []
  const completed = {
    status: 'completed',
    localRoot: 'C:\\ERP Files',
    selectedProjectRefs: ['project:p-1', 'audit:a-2'],
    completedFiles: 1,
    totalFiles: 1,
    failedFiles: 0,
    bytesDownloaded: 8,
    lastSuccessAt: '2026-07-27T10:05:00.000Z',
    message: '服务器资料已同步到本地',
  }
  registerDesktopIpcHandlers({
    ipcMain: harness.ipcMain,
    allowedOrigin: TRUSTED_ORIGIN,
    appVersion: '1.0.0',
    releaseChannel: 'development',
    controller: {
      getState: () => completed,
      async start() {
        await Promise.resolve()
        return completed
      },
      pause: () => ({ ...completed, status: 'paused' }),
      setLocalRoot: () => completed,
    },
    async selectFolder() {
      return ''
    },
    async openFolder() {},
    emitState: (state) => emitted.push(state),
  })
  const event = { senderFrame: { url: `${TRUSTED_ORIGIN}/#/materials` } }

  const returned = await harness.handlers.get(
    DESKTOP_IPC_CHANNELS.startSync
  )(event, validStartRequest())

  assert.deepEqual(returned, completed)
  assert.deepEqual(emitted, [completed])
  assert.equal(emitted[0] instanceof Promise, false)
})
