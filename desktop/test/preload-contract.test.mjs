import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDesktopBridge,
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
    'getCapabilities',
    'getSyncState',
    'onSyncState',
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
  assert.deepEqual(calls, [])

  const allowedBridge = createDesktopBridge(ipc, undefined, {
    isUserInitiated: () => true,
  })
  await allowedBridge.selectSyncFolder()
  await allowedBridge.openSyncFolder()
  assert.deepEqual(calls, [
    'desktop:select-sync-folder',
    'desktop:open-sync-folder',
  ])
})
