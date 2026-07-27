'use strict'

import { contextBridge, ipcRenderer } from 'electron'

import { createDesktopBridge } from './preload-contract.mjs'

const channels = Object.freeze({
  getCapabilities: 'desktop:get-capabilities',
  selectSyncFolder: 'desktop:select-sync-folder',
  getSyncState: 'desktop:get-sync-state',
  startSync: 'desktop:start-sync',
  pauseSync: 'desktop:pause-sync',
  openSyncFolder: 'desktop:open-sync-folder',
  syncState: 'desktop:sync-state',
})

contextBridge.exposeInMainWorld(
  'jiqingDesktop',
  createDesktopBridge({
    invoke: (channel, ...args) => ipcRenderer.invoke(channel, ...args),
    on: (channel, listener) => ipcRenderer.on(channel, listener),
    removeListener: (channel, listener) => {
      ipcRenderer.removeListener(channel, listener)
    },
  }, channels),
)
