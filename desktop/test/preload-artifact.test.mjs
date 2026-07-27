import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const mainSource = readFileSync(new URL('../src/main.mjs', import.meta.url), 'utf8')

function loadedPreloadName() {
  const match = mainSource.match(/preload:\s*join\(moduleRoot,\s*'([^']+)'\)/)
  assert.ok(match, 'main process must configure a preload artifact')
  return match[1]
}

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

test('main loads a sandbox-compatible single-file CommonJS preload artifact', () => {
  const preloadName = loadedPreloadName()
  assert.match(preloadName, /\.cjs$/)

  const preloadSource = readFileSync(
    new URL(`../src/${preloadName}`, import.meta.url),
    'utf8',
  )
  assert.doesNotMatch(preloadSource, /(?:^|\n)\s*(?:import|export)\s/m)

  let exposedName
  let exposedBridge
  const invocations = []
  const listeners = new Map()
  const electron = {
    contextBridge: {
      exposeInMainWorld(name, bridge) {
        exposedName = name
        exposedBridge = bridge
      },
    },
    ipcRenderer: {
      invoke(channel, ...args) {
        invocations.push([channel, ...args])
        return Promise.resolve(undefined)
      },
      on(channel, listener) {
        listeners.set(channel, listener)
      },
      removeListener(channel, listener) {
        if (listeners.get(channel) === listener) listeners.delete(channel)
      },
    },
  }

  runInNewContext(preloadSource, {
    Object,
    Promise,
    Set,
    TypeError,
    console: undefined,
    navigator: {
      userActivation: {
        isActive: true,
      },
    },
    require(specifier) {
      assert.equal(specifier, 'electron')
      return electron
    },
  }, { filename: preloadName })

  assert.equal(exposedName, 'jiqingDesktop')
  assert.deepEqual(
    Array.from(Object.keys(exposedBridge).sort()),
    [
      'getCapabilities',
      'getSyncState',
      'onSyncState',
      'openSyncFolder',
      'pauseSync',
      'selectSyncFolder',
      'startSync',
    ],
  )

  return Promise.all([
    exposedBridge.getCapabilities(),
    exposedBridge.selectSyncFolder(),
    exposedBridge.getSyncState(),
    exposedBridge.startSync({
      authToken: 'token',
      userId: 'user-1',
      projectRefs: [],
    }),
    exposedBridge.pauseSync(),
    exposedBridge.openSyncFolder(),
  ]).then(() => {
    assert.deepEqual(
      Array.from(invocations, ([channel]) => channel),
      [
        'desktop:get-capabilities',
        'desktop:select-sync-folder',
        'desktop:get-sync-state',
        'desktop:start-sync',
        'desktop:pause-sync',
        'desktop:open-sync-folder',
      ],
    )

    const received = []
    const cleanup = exposedBridge.onSyncState((state) => received.push(state))
    const listener = listeners.get('desktop:sync-state')
    assert.equal(typeof listener, 'function')
    listener({}, validState())
    listener({}, validState({ extra: true }))
    assert.equal(received.length, 1)
    cleanup()
    assert.equal(listeners.has('desktop:sync-state'), false)
  })
})
