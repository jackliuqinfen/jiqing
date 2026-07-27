import {
  app,
  BrowserWindow,
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
import { loadDesktopConfig } from './config.mjs'
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

const moduleRoot = fileURLToPath(new URL('.', import.meta.url))
const uiRoot = join(moduleRoot, '..', 'ui')
const config = loadDesktopConfig(process.env)
const sessionPartition = 'desktop-erp-memory'
let mainWindow = null

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

function protectWebContents(window) {
  const { webContents } = window
  const currentSession = webContents.session
  const navigationBlockedListeners = new Set()

  currentSession.setPermissionRequestHandler(
    (_webContents, _permission, callback) => callback(false),
  )
  currentSession.setPermissionCheckHandler(() => false)

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
      preload: join(moduleRoot, 'preload.mjs'),
      partition: sessionPartition,
    }),
  })

  const navigationGuard = protectWebContents(window)
  window.once('ready-to-show', () => window.show())
  window.on('close', () => saveWindowBounds(window))
  window.on('closed', () => {
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
}
