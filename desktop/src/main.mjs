import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  net,
  protocol,
  screen,
  session,
  shell,
} from 'electron'
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from 'node:fs'
import { dirname, join } from 'node:path'
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
import { pathsOverlap } from './sync/path-policy.mjs'
import {
  desktopWindowTitle,
  installEnvironmentTitleGuard,
} from './window-title.mjs'

const moduleRoot = fileURLToPath(new URL('.', import.meta.url))
const uiRoot = join(moduleRoot, '..', 'ui')
const unpackagedSmoke = (
  !app.isPackaged
  && process.env.DESKTOP_UNPACKAGED_SMOKE === '1'
)
const smokeCase = unpackagedSmoke
  ? String(process.env.DESKTOP_SMOKE_CASE || '')
  : ''
const smokeResultPath = unpackagedSmoke
  ? String(process.env.DESKTOP_SMOKE_RESULT || '')
  : ''
const smokeReadyPath = unpackagedSmoke
  ? String(process.env.DESKTOP_SMOKE_READY || '')
  : ''
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
const applicationDirectory = dirname(process.execPath)
let desktopIpcController = null
let mainWindow = null
let desktopIpcRegistered = false
let smokeCompleted = false

protocol.registerSchemesAsPrivileged([
  {
    scheme: 'app',
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: false,
    },
  },
])

app.on('certificate-error', (event, _webContents, _url, _error, _certificate, callback) => {
  event.preventDefault()
  callback(false)
})

function writeSmokeFile(path, value) {
  if (!unpackagedSmoke || !path) return
  mkdirSync(dirname(path), { recursive: true })
  const temporaryPath = `${path}.${process.pid}.tmp`
  writeFileSync(temporaryPath, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: 'utf8',
    mode: 0o600,
  })
  renameSync(temporaryPath, path)
}

function completeSmoke(result, exitCode = 0) {
  if (!unpackagedSmoke || smokeCompleted) return
  smokeCompleted = true
  writeSmokeFile(smokeResultPath, result)
  setImmediate(() => app.exit(exitCode))
}

function markSmokeReady() {
  if (!unpackagedSmoke || !smokeReadyPath) return
  writeSmokeFile(smokeReadyPath, { ready: true })
}

function currentLoadedOrigin(window) {
  try {
    return new URL(window.webContents.getURL()).origin
  } catch {
    return ''
  }
}

async function waitForTechnicalSmokePage(window) {
  const diagnostic = await window.webContents.executeJavaScript(
    `Promise.resolve(window.__desktopSmokeReady).then((ready) => ({
      ready: Boolean(ready),
      url: window.location.href,
      title: document.title,
      smokeReadyType: typeof window.__desktopSmokeReady,
    }))`,
    true,
  )
  if (diagnostic.ready !== true) {
    throw new Error(
      `technical smoke page did not initialize: ${JSON.stringify(diagnostic)}`,
    )
  }
}

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

function assertSafeSyncRoot(localRoot) {
  if (pathsOverlap(localRoot, applicationDirectory)) {
    throw new Error('sync root overlaps the application installation directory')
  }
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
  const selected = result.filePaths[0]
  try {
    assertSafeSyncRoot(selected)
  } catch {
    const messageOptions = {
      type: 'warning',
      title: '不能使用此文件夹',
      message: '同步文件夹不能与应用安装目录重叠',
      detail: '请选择“文档”等独立资料目录，避免卸载应用时误删同步文件。',
      buttons: ['重新选择'],
      defaultId: 0,
      noLink: true,
    }
    if (parent) {
      await dialog.showMessageBox(parent, messageOptions)
    } else {
      await dialog.showMessageBox(messageOptions)
    }
    return ''
  }
  return selected
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

async function loadApplication(
  window,
  navigationGuard,
  onHealthDiagnostic,
  onRemoteLoadError,
) {
  await window.loadURL('app://connecting/')
  const healthy = await checkRemoteHealth({
    fetchImpl: net.fetch,
    healthUrl: config.healthUrl,
    allowedOrigin: config.origin,
    onDiagnostic: onHealthDiagnostic,
    timeoutMs: config.healthTimeoutMs,
  })
  if (!healthy) {
    await window.loadURL('app://unavailable/').catch(() => {})
    return Object.freeze({
      healthReady: false,
      remoteLoaded: false,
    })
  }
  const remoteLoaded = await loadRemoteWithFallback({
    window,
    remoteUrl: config.origin,
    onLoadError: onRemoteLoadError,
    subscribeNavigationBlocked: navigationGuard.subscribeNavigationBlocked,
  })
  return Object.freeze({
    healthReady: true,
    remoteLoaded,
  })
}

async function createMainWindow() {
  const restoredBounds = readWindowBounds()
  const windowTitle = desktopWindowTitle(config.environmentLabel)
  const webPreferences = createSecureWebPreferences({
    preload: join(moduleRoot, 'preload.cjs'),
    partition: sessionPartition,
  })
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
    title: windowTitle,
    icon: join(app.getAppPath(), 'assets', 'icon.ico'),
    webPreferences,
  })

  const navigationGuard = protectWebContents(window)
  let smokeHealthDiagnostic = null
  let smokeRemoteLoadError = null
  const smokeBlockedNavigations = []
  const unsubscribeSmokeBlockedDiagnostics = unpackagedSmoke
    ? navigationGuard.subscribeNavigationBlocked(
        (target) => smokeBlockedNavigations.push(target),
      )
    : () => {}
  let smokeLoadFailure = null
  const captureSmokeLoadFailure = (
    _event,
    errorCode,
    errorDescription,
    validatedUrl,
    isMainFrame,
  ) => {
    if (!unpackagedSmoke || isMainFrame !== true) return
    smokeLoadFailure = {
      errorCode,
      errorDescription,
      validatedUrl,
    }
  }
  window.webContents.on('did-fail-load', captureSmokeLoadFailure)
  let smokeNavigationBlocked = null
  let resolveSmokeNavigationBlocked = null
  let unsubscribeSmokeNavigation = () => {}
  if (unpackagedSmoke && smokeCase === 'external-navigation') {
    smokeNavigationBlocked = new Promise((resolve) => {
      resolveSmokeNavigationBlocked = resolve
    })
    unsubscribeSmokeNavigation = navigationGuard.subscribeNavigationBlocked(
      (target) => resolveSmokeNavigationBlocked?.(target),
    )
  }
  installEnvironmentTitleGuard({
    webContents: window.webContents,
    window,
    environmentLabel: config.environmentLabel,
  })
  window.once('ready-to-show', () => window.show())
  window.on('close', () => saveWindowBounds(window))
  window.webContents.once('destroyed', () => {
    if (desktopIpcController) desktopIpcController.clearSession()
  })
  window.on('closed', () => {
    if (desktopIpcController) desktopIpcController.clearSession()
    if (mainWindow === window) mainWindow = null
  })

  const loadResult = await loadApplication(
    window,
    navigationGuard,
    (diagnostic) => {
      if (unpackagedSmoke) smokeHealthDiagnostic = diagnostic
    },
    (error) => {
      if (!unpackagedSmoke) return
      smokeRemoteLoadError = error instanceof Error
        ? { message: error.message, name: error.name }
        : { message: String(error), name: 'UnknownError' }
    },
  )
  window.webContents.removeListener(
    'did-fail-load',
    captureSmokeLoadFailure,
  )
  unsubscribeSmokeBlockedDiagnostics()
  if (unpackagedSmoke && smokeCase === 'successful-load') {
    if (!loadResult.remoteLoaded) {
      throw new Error(
        `technical remote load failed: ${JSON.stringify({
          blockedNavigations: smokeBlockedNavigations,
          healthDiagnostic: smokeHealthDiagnostic,
          loadFailure: smokeLoadFailure,
          remoteLoadError: smokeRemoteLoadError,
        })}`,
      )
    }
    await waitForTechnicalSmokePage(window)
    completeSmoke({
      healthReady: loadResult.healthReady,
      remoteLoaded: loadResult.remoteLoaded,
      nodeIntegration: webPreferences.nodeIntegration,
      contextIsolation: webPreferences.contextIsolation,
      sandbox: webPreferences.sandbox,
      loadedOrigin: currentLoadedOrigin(window),
    })
  } else if (unpackagedSmoke && smokeCase === 'server-unavailable') {
    completeSmoke({
      healthReady: loadResult.healthReady,
      remoteLoaded: loadResult.remoteLoaded,
      loadedUrl: window.webContents.getURL(),
    })
  } else if (
    unpackagedSmoke
    && smokeCase === 'external-navigation'
    && smokeNavigationBlocked
  ) {
    await waitForTechnicalSmokePage(window)
    const blockedUrl = await smokeNavigationBlocked
    unsubscribeSmokeNavigation()
    completeSmoke({
      externalNavigationDenied: true,
      blockedUrl,
      loadedOrigin: currentLoadedOrigin(window),
    })
  }
  return window
}

const ownsSingleInstance = app.requestSingleInstanceLock()
if (!ownsSingleInstance) {
  if (unpackagedSmoke && smokeCase === 'second-instance-secondary') {
    completeSmoke({ ownsSingleInstance: false })
  }
  app.quit()
} else {
  app.on('second-instance', () => {
    if (!mainWindow || mainWindow.isDestroyed()) return
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.show()
    mainWindow.focus()
    if (unpackagedSmoke && smokeCase === 'second-instance-primary') {
      completeSmoke({ secondInstanceFocused: true })
    }
  })

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null)
    const desktopSession = session.fromPartition(sessionPartition)
    registerAppProtocol(
      desktopSession.protocol,
      net,
      uiRoot,
    )
    const apiClient = new DesktopApiClient({
      origin: config.origin,
      fetchImpl: net.fetch,
    })
    const syncEngine = new SyncEngine({
      apiClient,
      appDataPath: app.getPath('userData'),
      environmentOrigin: config.origin,
      emitState: emitDesktopSyncState,
      installationDirectory: applicationDirectory,
    })
    desktopIpcController = createDesktopIpcController({ syncEngine })
    registerDesktopBridge()
    mainWindow = await createMainWindow()
    if (unpackagedSmoke && smokeCase === 'second-instance-primary') {
      markSmokeReady()
    }

    app.on('activate', async () => {
      if (!mainWindow) mainWindow = await createMainWindow()
    })
  }).catch((error) => {
    if (unpackagedSmoke) {
      completeSmoke({
        runtimeError: error instanceof Error ? error.message : 'unknown error',
      }, 1)
    } else {
      app.quit()
    }
  })

  app.on('window-all-closed', () => {
    app.quit()
  })

  app.on('before-quit', () => {
    if (desktopIpcController) desktopIpcController.clearSession()
  })
}
