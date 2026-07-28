import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDesktopBridge,
  validateDesktopUpdateState,
  validateWorkspaceCommand,
  validateDesktopSyncState,
} from '../src/preload-contract.mjs'

function validState(overrides = {}) {
  return {
    status: 'paused',
    localRoot: '',
    selectedProjectRefs: [],
    completedFiles: 0,
    totalFiles: 0,
    failedFiles: 0,
    bytesDownloaded: 0,
    lastSuccessAt: '',
    message: '本地同步尚未启动',
    ...overrides,
  }
}

function validUpdateState(overrides = {}) {
  return {
    status: 'idle',
    currentVersion: '1.0.3',
    availableVersion: '',
    progressPercent: 0,
    canCheck: true,
    canInstall: false,
    lastCheckedAt: '',
    message: '可检查是否有新的客户端版本',
    ...overrides,
  }
}

test('desktop state validation accepts the exact conservative shape', () => {
  assert.deepEqual(validateDesktopSyncState(validState()), validState())
})

test('desktop state validation rejects malformed or extra payloads', () => {
  for (const state of [
    null,
    [],
    validState({ extra: true }),
    validState({ status: 'made_up' }),
    validState({ localRoot: 3 }),
    validState({ selectedProjectRefs: ['invalid'] }),
    validState({ completedFiles: -1 }),
    validState({ totalFiles: 0.5 }),
    validState({ bytesDownloaded: Number.POSITIVE_INFINITY }),
    validState({ message: 'x'.repeat(4097) }),
  ]) {
    assert.equal(validateDesktopSyncState(state), null)
  }
})

test('desktop update validation accepts only the exact bounded state', () => {
  assert.deepEqual(
    validateDesktopUpdateState(validUpdateState()),
    validUpdateState(),
  )
  for (const state of [
    null,
    validUpdateState({ extra: true }),
    validUpdateState({ status: 'made_up' }),
    validUpdateState({ currentVersion: '' }),
    validUpdateState({ progressPercent: 101 }),
    validUpdateState({ canCheck: 'yes' }),
    validUpdateState({ message: 'x'.repeat(1025) }),
  ]) {
    assert.equal(validateDesktopUpdateState(state), null)
  }
})

test('workspace command validation accepts only the fixed desktop command set', () => {
  for (const command of [
    'workspace:back',
    'workspace:forward',
    'workspace:command-center',
    'workspace:restore-closed-tab',
  ]) {
    assert.equal(validateWorkspaceCommand(command), command)
  }
  for (const command of ['', 'workspace:open-url', '/project-management', null]) {
    assert.equal(validateWorkspaceCommand(command), null)
  }
})

test('bridge exposes only narrow operations and filters state events', async () => {
  const invocations = []
  let eventListener
  let removed
  const bridge = createDesktopBridge({
    invoke(channel, ...args) {
      invocations.push([channel, ...args])
      return Promise.resolve(undefined)
    },
    on(channel, listener) {
      eventListener = listener
      invocations.push(['on', channel])
    },
    removeListener(channel, listener) {
      removed = [channel, listener]
    },
  })

  assert.deepEqual(Object.keys(bridge).sort(), [
    'checkForUpdates',
    'getCapabilities',
    'getSyncState',
    'getUpdateState',
    'installUpdate',
    'onSyncState',
    'onUpdateState',
    'onWorkspaceCommand',
    'openSyncFolder',
    'pauseSync',
    'selectSyncFolder',
    'startSync',
  ])
  await bridge.getCapabilities()
  await bridge.startSync({
    authToken: 'token',
    userId: 'user-1',
    projectRefs: [],
  })

  const received = []
  const cleanup = bridge.onSyncState((state) => received.push(state))
  eventListener({}, validState())
  eventListener({}, validState({ status: 'invalid' }))
  assert.equal(received.length, 1)

  cleanup()
  assert.equal(removed[0], 'desktop:sync-state')
  assert.equal(removed[1], eventListener)
  assert.deepEqual(invocations.slice(0, 2), [
    ['desktop:get-capabilities'],
    [
      'desktop:start-sync',
      { authToken: 'token', userId: 'user-1', projectRefs: [] },
    ],
  ])

  const workspaceCommands = []
  const commandCleanup = bridge.onWorkspaceCommand(
    (command) => workspaceCommands.push(command),
  )
  eventListener({}, 'workspace:back')
  eventListener({}, 'workspace:open-url')
  assert.deepEqual(workspaceCommands, ['workspace:back'])
  commandCleanup()
})

test('state subscription requires a function listener', () => {
  const bridge = createDesktopBridge({
    invoke() {
      return Promise.resolve()
    },
    on() {},
    removeListener() {},
  })

  assert.throws(() => bridge.onSyncState(null), /listener/i)
  assert.throws(() => bridge.onWorkspaceCommand(null), /listener/i)
})

test('folder actions require an active user gesture in the isolated preload', async () => {
  const calls = []
  const ipc = {
    invoke(channel) {
      calls.push(channel)
      return Promise.resolve()
    },
    on() {},
    removeListener() {},
  }
  const deniedBridge = createDesktopBridge(ipc, undefined, {
    isUserInitiated: () => false,
  })

  await assert.rejects(deniedBridge.selectSyncFolder(), /user activation/i)
  await assert.rejects(deniedBridge.openSyncFolder(), /user activation/i)
  await assert.rejects(deniedBridge.checkForUpdates(), /user activation/i)
  await assert.rejects(deniedBridge.installUpdate(), /user activation/i)
  assert.deepEqual(calls, [])

  const allowedBridge = createDesktopBridge(ipc, undefined, {
    isUserInitiated: () => true,
  })
  await allowedBridge.selectSyncFolder()
  await allowedBridge.openSyncFolder()
  await allowedBridge.checkForUpdates()
  await allowedBridge.installUpdate()
  assert.deepEqual(calls, [
    'desktop:select-sync-folder',
    'desktop:open-sync-folder',
    'desktop:check-for-updates',
    'desktop:install-update',
  ])
})

test('update subscription filters malformed renderer payloads', () => {
  const listeners = new Map()
  const received = []
  const bridge = createDesktopBridge({
    invoke() {
      return Promise.resolve()
    },
    on(channel, listener) {
      listeners.set(channel, listener)
    },
    removeListener(channel) {
      listeners.delete(channel)
    },
  })

  const cleanup = bridge.onUpdateState((state) => received.push(state))
  listeners.get('desktop:update-state')({}, validUpdateState())
  listeners.get('desktop:update-state')({}, validUpdateState({ status: 'fake' }))
  assert.equal(received.length, 1)
  cleanup()
  assert.equal(listeners.has('desktop:update-state'), false)
})
