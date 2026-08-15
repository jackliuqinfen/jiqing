import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  net,
  Notification,
  protocol,
  screen,
  session,
  shell,
} from 'electron'
import electronUpdater from 'electron-updater'
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  registerAppProtocol,
  resolveAppPage,
} from './app-protocol.mjs'
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
import {
  closeEnterpriseSplashWindow,
  createEnterpriseSplashWindow,
  SPLASH_PARTITION,
} from './splash-window.mjs'
import { DesktopApiClient } from './sync/api-client.mjs'
import { SyncEngine } from './sync/sync-engine.mjs'
import { pathsOverlap } from './sync/path-policy.mjs'
import { SyncScheduler } from './sync/sync-scheduler.mjs'
import {
  desktopWindowTitle,
  installEnvironmentTitleGuard,
} from './window-title.mjs'
import {
  createIntegratedTitleBarOptions,
  hasLiveWindowWebContents,
  INTEGRATED_TITLE_BAR_CSS,
} from './window-chrome.mjs'
import {
  createWindowsMenuTemplate,
  syncPresentation,
} from './windows-integration.mjs'
import {
  readDesktopPreferences,
  writeDesktopPreferences,
} from './desktop-preferences.mjs'
import { createDesktopUpdateController } from './update-controller.mjs'

const { autoUpdater } = electronUpdater

const moduleRoot = fileURLToPath(new URL('.', import.meta.url))
const uiRoot = join(moduleRoot, '..', 'ui')
const assetsRoot = join(moduleRoot, '..', 'assets')
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
let desktopSyncScheduler = null
let desktopUpdateController = null
let mainWindow = null
let splashWindow = null
let desktopIpcRegistered = false
let smokeCompleted = false
let lastMenuStateKey = ''
let lastSyncStatus = ''

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
  try {
    const preferences = readDesktopPreferences(app.getPath('userData'))
    writeDesktopPreferences(app.getPath('userData'), { ...preferences, localRoot: selected })
  } catch {
    // A selected folder remains usable for this session even if preferences
    // cannot be persisted because of an operating-system permission issue.
  }
  return selected
}

async function openDesktopSyncFolder(localRoot) {
  const errorMessage = await shell.openPath(localRoot)
  if (errorMessage) throw new Error('unable to open sync folder')
}

function navigateDesktopModule(path, query = '') {
  if (!mainWindow || mainWindow.isDestroyed()) return
  const target = new URL(config.origin)
  target.hash = `${path}${query}`
  void mainWindow.loadURL(target.href).catch(() => {})
}

function emitWorkspaceCommand(command) {
  const window = mainWindow
  if (!hasLiveWindowWebContents(window)) return
  if (!isAllowedNavigation(window.webContents.getURL(), config.origin)) return
  window.webContents.send(DESKTOP_IPC_CHANNELS.workspaceCommand, command)
}

async function chooseSyncFolderFromMenu() {
  if (!desktopIpcController) return
  const selected = await selectDesktopSyncFolder()
  if (!selected) return
  emitDesktopSyncState(desktopIpcController.setLocalRoot(selected))
}

async function openSyncFolderFromMenu() {
  const localRoot = desktopIpcController?.getState().localRoot
  if (!localRoot) return
  await openDesktopSyncFolder(localRoot)
}

async function pauseSyncFromMenu() {
  if (!desktopIpcController) return
  emitDesktopSyncState(await desktopIpcController.pause())
}

async function showDesktopAbout() {
  const options = {
    type: 'info',
    title: '关于集庆工程管理',
    message: '集庆工程管理',
    detail: [
      `版本 ${app.getVersion()}`,
      `发布通道：${config.releaseChannel}`,
      '项目、资料、审计与结算一体化 Windows 工作台',
    ].join('\n'),
    buttons: ['确定'],
    defaultId: 0,
    noLink: true,
    icon: join(assetsRoot, 'icon.ico'),
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    await dialog.showMessageBox(mainWindow, options)
  } else {
    await dialog.showMessageBox(options)
  }
}

function installWindowsApplicationMenu(force = false) {
  if (!desktopIpcController || !mainWindow || mainWindow.isDestroyed()) return
  const state = desktopIpcController.getState()
  const stateKey = `${state.status}:${state.localRoot ? 'folder' : 'none'}`
  if (!force && stateKey === lastMenuStateKey) return
  lastMenuStateKey = stateKey
  const template = createWindowsMenuTemplate({
    state,
    actions: {
      navigate: (path) => navigateDesktopModule(path),
      dispatchWorkspaceCommand: (command) => emitWorkspaceCommand(command),
      openSyncSettings: () => navigateDesktopModule(
        '/materials',
        `?desktopSync=${Date.now()}`,
      ),
      selectSyncFolder: () => void chooseSyncFolderFromMenu(),
      openSyncFolder: () => void openSyncFolderFromMenu(),
      pauseSync: () => void pauseSyncFromMenu(),
      showAbout: () => void showDesktopAbout(),
    },
  })
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
  mainWindow.setMenuBarVisibility(true)
}

function applyWindowsSyncFeedback(state) {
  if (!mainWindow || mainWindow.isDestroyed()) return
  const presentation = syncPresentation(state, lastSyncStatus)
  lastSyncStatus = state.status
  mainWindow.setProgressBar(
    presentation.progress,
    presentation.progressMode === 'none'
      ? undefined
      : { mode: presentation.progressMode },
  )
  if (
    presentation.notification
    && !unpackagedSmoke
    && Notification.isSupported()
  ) {
    new Notification({
      ...presentation.notification,
      icon: join(assetsRoot, 'icon.ico'),
      silent: true,
    }).show()
  }
  installWindowsApplicationMenu()
}

function emitDesktopSyncState(state) {
  const window = mainWindow
  if (!hasLiveWindowWebContents(window)) return
  applyWindowsSyncFeedback(state)
  if (!isAllowedNavigation(window.webContents.getURL(), config.origin)) return
  window.webContents.send(DESKTOP_IPC_CHANNELS.syncState, state)
}

function emitDesktopUpdateState(state) {
  const window = mainWindow
  if (!hasLiveWindowWebContents(window)) return
  if (!isAllowedNavigation(window.webContents.getURL(), config.origin)) return
  window.webContents.send(DESKTOP_IPC_CHANNELS.updateState, state)
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
    syncScheduler: desktopSyncScheduler,
    updateController: desktopUpdateController,
    selectFolder: selectDesktopSyncFolder,
    openFolder: openDesktopSyncFolder,
    onSyncStart: (request) => {
      const preferences = readDesktopPreferences(app.getPath('userData'))
      writeDesktopPreferences(app.getPath('userData'), {
        ...preferences,
        selectedProjectRefs: request.projectRefs,
      })
    },
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
        desktopSyncScheduler?.stop()
        desktopIpcController.clearSession()
      }
      callback({})
    },
  )

  const guardNavigation = (event, target) => {
    if (
      isAllowedNavigation(target, config.origin)
      || resolveAppPage(target, uiRoot)
    ) {
      return
    }
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
    autoHideMenuBar: false,
    backgroundColor: '#F8FBFF',
    show: false,
    title: windowTitle,
    ...createIntegratedTitleBarOptions(),
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
  window.on('close', () => saveWindowBounds(window))
  window.on('app-command', (_event, command) => {
    if (command === 'browser-backward') emitWorkspaceCommand('workspace:back')
    if (command === 'browser-forward') emitWorkspaceCommand('workspace:forward')
  })
  window.webContents.once('destroyed', () => {
    if (mainWindow === window) mainWindow = null
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
  await window.webContents.insertCSS(INTEGRATED_TITLE_BAR_CSS)
  window.webContents.on('did-finish-load', () => {
    void window.webContents.insertCSS(INTEGRATED_TITLE_BAR_CSS)
  })
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
    app.setAppUserModelId('com.jiqing.erp')
    const desktopSession = session.fromPartition(sessionPartition)
    registerAppProtocol(
      desktopSession.protocol,
      net,
      uiRoot,
      assetsRoot,
    )
    if (!unpackagedSmoke) {
      const splashSession = session.fromPartition(SPLASH_PARTITION)
      registerAppProtocol(
        splashSession.protocol,
        net,
        uiRoot,
        assetsRoot,
      )
      splashWindow = await createEnterpriseSplashWindow({
        BrowserWindow,
        iconPath: join(assetsRoot, 'icon.ico'),
      })
    }
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
    desktopSyncScheduler = new SyncScheduler({
      controller: desktopIpcController,
      apiClient,
    })
    desktopUpdateController = createDesktopUpdateController({
      currentVersion: app.getVersion(),
      enabled: (
        app.isPackaged
        && process.platform === 'win32'
        && config.releaseChannel !== 'development'
      ),
      updater: autoUpdater,
      emitState: emitDesktopUpdateState,
    })
    const preferences = readDesktopPreferences(app.getPath('userData'))
    if (preferences.localRoot) {
      try {
        assertSafeSyncRoot(preferences.localRoot)
        desktopIpcController.setLocalRoot(preferences.localRoot)
      } catch {
        // Ignore a stale or newly unsafe path and let the user select again.
      }
    }
    desktopIpcController.setSelectedProjectRefs(preferences.selectedProjectRefs)
    registerDesktopBridge()
    mainWindow = await createMainWindow()
    installWindowsApplicationMenu(true)
    if (!mainWindow.isDestroyed()) {
      mainWindow.show()
      mainWindow.focus()
    }
    closeEnterpriseSplashWindow(splashWindow)
    splashWindow = null
    if (unpackagedSmoke && smokeCase === 'second-instance-primary') {
      markSmokeReady()
    }

    app.on('activate', async () => {
      if (!mainWindow) mainWindow = await createMainWindow()
    })
  }).catch((error) => {
    closeEnterpriseSplashWindow(splashWindow)
    splashWindow = null
    console.error('desktop startup failed', error)
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
    if (desktopSyncScheduler) desktopSyncScheduler.stop()
    if (desktopIpcController) desktopIpcController.clearSession()
  })
}
