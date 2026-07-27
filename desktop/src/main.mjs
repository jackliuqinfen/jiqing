import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  net,
  protocol,
  screen,
  shell,
} from 'electron'
import {
  existsSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { registerAppProtocol } from './app-protocol.mjs'
import {
  loadDesktopConfig,
  readEmbeddedReleaseProfile,
} from './config.mjs'
import {
  createDesktopIpcController,
  DESKTOP_IPC_CHANNELS,
  registerDesktopIpcHandlers,
} from './ipc-contract.mjs'
import {
  checkRemoteHealth,
  loadRemoteWithFallback,
} from './remote-load.mjs'
import {
  createSecureWebPreferences,
  isAllowedNavigation,
  isReviewedExternalUrl,
  normalizeWindowBounds,
} from './security.mjs'
import { DesktopApiClient } from './sync/api-client.mjs'
import { SyncEngine } from './sync/sync-engine.mjs'

const moduleRoot = fileURLToPath(new URL('.', import.meta.url))
const uiRoot = join(moduleRoot, '..', 'ui')
const embeddedProfile = app.isPackaged
  ? readEmbeddedReleaseProfile(
      new URL('./release-profile.generated.json', import.meta.url),
    )
  : null
const config = loadDesktopConfig({
  embeddedProfile,
  env: process.env,
  isPackaged: app.isPackaged,
})
const sessionPartition = 'desktop-erp-memory'
let desktopIpcController = null
let mainWindow = null
let desktopIpcRegistered = false

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: false,
    },
  },
])

app.on('certificate-error', (event, _webContents, _url, _error, _certificate, callback) => {
  event.preventDefault()
  callback(false)
})

function windowStatePath() {
  return join(app.getPath('userData'), 'window-state.json')
}

function readWindowBounds() {
  const statePath = windowStatePath()
  if (!existsSync(statePath)) return null

  try {
    const parsed = JSON.parse(readFileSync(statePath, 'utf8'))
    return normalizeWindowBounds(parsed, screen.getAllDisplays())
  } catch {
    return null
  }
}

function saveWindowBounds(window) {
  if (!window || window.isDestroyed()) return

  const candidate = window.isMaximized()
    ? window.getNormalBounds()
    : window.getBounds()
  const bounds = normalizeWindowBounds(candidate, screen.getAllDisplays())
  if (!bounds) return

  const statePath = windowStatePath()
  const temporaryPath = `${statePath}.tmp`
  try {
    writeFileSync(temporaryPath, JSON.stringify(bounds), {
      encoding: 'utf8',
      mode: 0o600,
    })
    renameSync(temporaryPath, statePath)
  } catch {
    // Window state is optional. Startup must not fail when it cannot be saved.
  }
}

function openReviewedExternalUrl(target) {
  if (!isReviewedExternalUrl(target, config.origin)) return
  void shell.openExternal(target, { activate: true }).catch(() => {})
}

async function selectDesktopSyncFolder() {
  const options = {
    title: '选择本地资料同步文件夹',
    buttonLabel: '选择此文件夹',
    properties: ['openDirectory', 'createDirectory'],
  }
  const parent = mainWindow && !mainWindow.isDestroyed()
    ? mainWindow
    : null
  const result = parent
    ? await dialog.showOpenDialog(parent, options)
    : await dialog.showOpenDialog(options)
  if (result.canceled || result.filePaths.length !== 1) return ''
  return result.filePaths[0]
}

async function openDesktopSyncFolder(localRoot) {
  const errorMessage = await shell.openPath(localRoot)
  if (errorMessage) throw new Error('unable to open sync folder')
}

function emitDesktopSyncState(state) {
  if (!mainWindow || mainWindow.isDestroyed()) return
  if (!isAllowedNavigation(mainWindow.webContents.getURL(), config.origin)) return
  mainWindow.webContents.send(DESKTOP_IPC_CHANNELS.syncState, state)
}

function registerDesktopBridge() {
  if (desktopIpcRegistered) return
  if (!desktopIpcController) {
    throw new Error('desktop synchronization engine is not ready')
  }
  registerDesktopIpcHandlers({
    ipcMain,
    allowedOrigin: config.origin,
    appVersion: app.getVersion(),
    releaseChannel: config.releaseChannel,
    controller: desktopIpcController,
    selectFolder: selectDesktopSyncFolder,
    openFolder: openDesktopSyncFolder,
    emitState: emitDesktopSyncState,
  })
  desktopIpcRegistered = true
}

function protectWebContents(window) {
  const { webContents } = window
  const currentSession = webContents.session
  const navigationBlockedListeners = new Set()

  currentSession.setPermissionRequestHandler(
    (_webContents, _permission, callback) => callback(false),
  )
  currentSession.setPermissionCheckHandler(() => false)
  currentSession.webRequest.onBeforeRequest(
    { urls: [`${config.origin}/api/auth/logout`] },
    (details, callback) => {
      if (details.method === 'POST' && desktopIpcController) {
        desktopIpcController.clearSession()
      }
      callback({})
    },
  )

  const guardNavigation = (event, target) => {
    if (isAllowedNavigation(target, config.origin)) return
    event.preventDefault()
    for (const listener of navigationBlockedListeners) listener(target)
    openReviewedExternalUrl(target)
  }
  webContents.on('will-navigate', guardNavigation)
  webContents.on('will-redirect', guardNavigation)
  webContents.setWindowOpenHandler(({ url }) => {
    openReviewedExternalUrl(url)
    return { action: 'deny' }
  })

  return {
    subscribeNavigationBlocked(listener) {
      navigationBlockedListeners.add(listener)
      return () => navigationBlockedListeners.delete(listener)
    },
  }
}

async function loadApplication(window, navigationGuard) {
  await window.loadURL('app://connecting')
  const healthy = await checkRemoteHealth({
    fetchImpl: net.fetch,
    healthUrl: config.healthUrl,
    allowedOrigin: config.origin,
    timeoutMs: config.healthTimeoutMs,
  })
  if (!healthy) {
    await window.loadURL('app://unavailable').catch(() => {})
    return
  }
  await loadRemoteWithFallback({
    window,
    remoteUrl: config.origin,
    subscribeNavigationBlocked: navigationGuard.subscribeNavigationBlocked,
  })
}

async function createMainWindow() {
  const restoredBounds = readWindowBounds()
  const window = new BrowserWindow({
    width: restoredBounds?.width ?? 1440,
    height: restoredBounds?.height ?? 900,
    ...(restoredBounds
      ? { x: restoredBounds.x, y: restoredBounds.y }
      : {}),
    minWidth: 1100,
    minHeight: 720,
    autoHideMenuBar: true,
    show: false,
    title: config.environmentLabel
      ? `集庆工程管理 - ${config.environmentLabel}`
      : '集庆工程管理',
    icon: join(app.getAppPath(), 'assets', 'icon.ico'),
    webPreferences: createSecureWebPreferences({
      preload: join(moduleRoot, 'preload.cjs'),
      partition: sessionPartition,
    }),
  })

  const navigationGuard = protectWebContents(window)
  window.once('ready-to-show', () => window.show())
  window.on('close', () => saveWindowBounds(window))
  window.webContents.once('destroyed', () => {
    if (desktopIpcController) desktopIpcController.clearSession()
  })
  window.on('closed', () => {
    if (desktopIpcController) desktopIpcController.clearSession()
    if (mainWindow === window) mainWindow = null
  })

  await loadApplication(window, navigationGuard)
  return window
}

const ownsSingleInstance = app.requestSingleInstanceLock()
if (!ownsSingleInstance) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.show()
    mainWindow.focus()
  })

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null)
    registerAppProtocol(protocol, net, uiRoot)
    const apiClient = new DesktopApiClient({
      origin: config.origin,
      fetchImpl: net.fetch,
    })
    const syncEngine = new SyncEngine({
      apiClient,
      appDataPath: app.getPath('userData'),
      environmentOrigin: config.origin,
      emitState: emitDesktopSyncState,
    })
    desktopIpcController = createDesktopIpcController({ syncEngine })
    registerDesktopBridge()
    mainWindow = await createMainWindow()

    app.on('activate', async () => {
      if (!mainWindow) mainWindow = await createMainWindow()
    })
  }).catch(() => {
    app.quit()
  })

  app.on('window-all-closed', () => {
    app.quit()
  })

  app.on('before-quit', () => {
    if (desktopIpcController) desktopIpcController.clearSession()
  })
}
