'use strict'

const { contextBridge, ipcRenderer } = require('electron')

const channels = Object.freeze({
  getCapabilities: 'desktop:get-capabilities',
  selectSyncFolder: 'desktop:select-sync-folder',
  getSyncState: 'desktop:get-sync-state',
  startSync: 'desktop:start-sync',
  pauseSync: 'desktop:pause-sync',
  openSyncFolder: 'desktop:open-sync-folder',
  syncState: 'desktop:sync-state',
})
const syncStatuses = new Set([
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
const stateKeys = Object.freeze([
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
const projectRefPattern = /^(project|audit):[A-Za-z0-9-]+$/

function isPlainObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

function hasExactStateKeys(value) {
  const keys = Object.keys(value).sort()
  return (
    keys.length === stateKeys.length
    && keys.every((key, index) => key === stateKeys[index])
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
      || !projectRefPattern.test(reference)
      || seen.has(reference)
    ) {
      return null
    }
    seen.add(reference)
  }
  return Object.freeze([...value])
}

function validateDesktopSyncState(value) {
  if (!isPlainObject(value) || !hasExactStateKeys(value)) return null
  const selectedProjectRefs = validateRefs(value.selectedProjectRefs)
  if (
    !syncStatuses.has(value.status)
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

function invokeUserAction(channel) {
  if (globalThis.navigator?.userActivation?.isActive !== true) {
    return Promise.reject(new Error('desktop action requires user activation'))
  }
  return ipcRenderer.invoke(channel)
}

const bridge = Object.freeze({
  getCapabilities: () => ipcRenderer.invoke(channels.getCapabilities),
  selectSyncFolder: () => invokeUserAction(channels.selectSyncFolder),
  getSyncState: () => ipcRenderer.invoke(channels.getSyncState),
  startSync: (request) => ipcRenderer.invoke(channels.startSync, request),
  pauseSync: () => ipcRenderer.invoke(channels.pauseSync),
  openSyncFolder: () => invokeUserAction(channels.openSyncFolder),
  onSyncState(listener) {
    if (typeof listener !== 'function') {
      throw new TypeError('sync state listener must be a function')
    }
    const guardedListener = (_event, payload) => {
      const state = validateDesktopSyncState(payload)
      if (state) listener(state)
    }
    ipcRenderer.on(channels.syncState, guardedListener)
    return () => {
      ipcRenderer.removeListener(channels.syncState, guardedListener)
    }
  },
})

contextBridge.exposeInMainWorld('jiqingDesktop', bridge)
