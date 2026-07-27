import { DESKTOP_IPC_CHANNELS } from './ipc-contract.mjs'

const SYNC_STATUSES = new Set([
  'disabled',
  'waiting_for_login',
  'checking_policy',
  'syncing',
  'paused',
  'completed',
  'partial_failure',
  'permission_changed',
  'offline',
])
const STATE_KEYS = Object.freeze([
  'bytesDownloaded',
  'completedFiles',
  'failedFiles',
  'lastSuccessAt',
  'localRoot',
  'message',
  'selectedProjectRefs',
  'status',
  'totalFiles',
])
const PROJECT_REF_PATTERN = /^(project|audit):[A-Za-z0-9-]+$/

function isPlainObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

function hasExactStateKeys(value) {
  const keys = Object.keys(value).sort()
  return (
    keys.length === STATE_KEYS.length
    && keys.every((key, index) => key === STATE_KEYS[index])
  )
}

function isSafeCount(value) {
  return Number.isSafeInteger(value) && value >= 0
}

function validateRefs(value) {
  if (!Array.isArray(value) || value.length > 500) return null
  const seen = new Set()
  for (const reference of value) {
    if (
      typeof reference !== 'string'
      || !PROJECT_REF_PATTERN.test(reference)
      || seen.has(reference)
    ) {
      return null
    }
    seen.add(reference)
  }
  return Object.freeze([...value])
}

export function validateDesktopSyncState(value) {
  if (!isPlainObject(value) || !hasExactStateKeys(value)) return null
  const selectedProjectRefs = validateRefs(value.selectedProjectRefs)
  if (
    !SYNC_STATUSES.has(value.status)
    || typeof value.localRoot !== 'string'
    || value.localRoot.length > 32767
    || selectedProjectRefs === null
    || !isSafeCount(value.completedFiles)
    || !isSafeCount(value.totalFiles)
    || !isSafeCount(value.failedFiles)
    || !isSafeCount(value.bytesDownloaded)
    || value.completedFiles + value.failedFiles > value.totalFiles
    || typeof value.lastSuccessAt !== 'string'
    || value.lastSuccessAt.length > 64
    || typeof value.message !== 'string'
    || value.message.length > 4096
  ) {
    return null
  }

  return Object.freeze({
    status: value.status,
    localRoot: value.localRoot,
    selectedProjectRefs,
    completedFiles: value.completedFiles,
    totalFiles: value.totalFiles,
    failedFiles: value.failedFiles,
    bytesDownloaded: value.bytesDownloaded,
    lastSuccessAt: value.lastSuccessAt,
    message: value.message,
  })
}

export function createDesktopBridge(
  ipc,
  channels = DESKTOP_IPC_CHANNELS,
  {
    isUserInitiated = () => (
      globalThis.navigator?.userActivation?.isActive === true
    ),
  } = {},
) {
  const invoke = (channel, ...args) => ipc.invoke(channel, ...args)
  const invokeUserAction = (channel) => {
    if (!isUserInitiated()) {
      return Promise.reject(new Error('desktop action requires user activation'))
    }
    return invoke(channel)
  }

  return Object.freeze({
    getCapabilities: () => invoke(channels.getCapabilities),
    selectSyncFolder: () => invokeUserAction(channels.selectSyncFolder),
    getSyncState: () => invoke(channels.getSyncState),
    startSync: (request) => invoke(channels.startSync, request),
    pauseSync: () => invoke(channels.pauseSync),
    openSyncFolder: () => invokeUserAction(channels.openSyncFolder),
    onSyncState(listener) {
      if (typeof listener !== 'function') {
        throw new TypeError('sync state listener must be a function')
      }
      const guardedListener = (_event, payload) => {
        const state = validateDesktopSyncState(payload)
        if (state) listener(state)
      }
      ipc.on(channels.syncState, guardedListener)
      return () => {
        ipc.removeListener(channels.syncState, guardedListener)
      }
    },
  })
}
