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
const WORKSPACE_COMMANDS = new Set([
  'workspace:back',
  'workspace:forward',
  'workspace:command-center',
  'workspace:restore-closed-tab',
])
const UPDATE_STATUSES = new Set([
  'unavailable',
  'idle',
  'checking',
  'available',
  'downloading',
  'downloaded',
  'up_to_date',
  'error',
])
const UPDATE_STATE_KEYS = Object.freeze([
  'availableVersion',
  'canCheck',
  'canInstall',
  'currentVersion',
  'lastCheckedAt',
  'message',
  'progressPercent',
  'status',
])

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

export function validateWorkspaceCommand(value) {
  return typeof value === 'string' && WORKSPACE_COMMANDS.has(value)
    ? value
    : null
}

export function validateDesktopUpdateState(value) {
  if (!isPlainObject(value)) return null
  const keys = Object.keys(value).sort()
  if (
    keys.length !== UPDATE_STATE_KEYS.length
    || !keys.every((key, index) => key === UPDATE_STATE_KEYS[index])
    || !UPDATE_STATUSES.has(value.status)
    || typeof value.currentVersion !== 'string'
    || value.currentVersion.length < 1
    || value.currentVersion.length > 64
    || typeof value.availableVersion !== 'string'
    || value.availableVersion.length > 64
    || !Number.isInteger(value.progressPercent)
    || value.progressPercent < 0
    || value.progressPercent > 100
    || typeof value.canCheck !== 'boolean'
    || typeof value.canInstall !== 'boolean'
    || typeof value.lastCheckedAt !== 'string'
    || value.lastCheckedAt.length > 64
    || typeof value.message !== 'string'
    || value.message.length > 1024
  ) {
    return null
  }
  return Object.freeze({ ...value })
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
    getUpdateState: () => invoke(channels.getUpdateState),
    checkForUpdates: () => invokeUserAction(channels.checkForUpdates),
    installUpdate: () => invokeUserAction(channels.installUpdate),
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
    onWorkspaceCommand(listener) {
      if (typeof listener !== 'function') {
        throw new TypeError('workspace command listener must be a function')
      }
      const guardedListener = (_event, payload) => {
        const command = validateWorkspaceCommand(payload)
        if (command) listener(command)
      }
      ipc.on(channels.workspaceCommand, guardedListener)
      return () => {
        ipc.removeListener(channels.workspaceCommand, guardedListener)
      }
    },
    onUpdateState(listener) {
      if (typeof listener !== 'function') {
        throw new TypeError('update state listener must be a function')
      }
      const guardedListener = (_event, payload) => {
        const state = validateDesktopUpdateState(payload)
        if (state) listener(state)
      }
      ipc.on(channels.updateState, guardedListener)
      return () => {
        ipc.removeListener(channels.updateState, guardedListener)
      }
    },
  })
}
