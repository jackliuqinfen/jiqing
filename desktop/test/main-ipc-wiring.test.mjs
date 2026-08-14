import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const main = readFileSync(
  new URL('../src/main.mjs', import.meta.url),
  'utf8',
)

test('main process registers the bounded desktop IPC controller', () => {
  assert.match(main, /registerDesktopIpcHandlers/)
  assert.match(main, /createDesktopIpcController/)
  assert.match(main, /new SyncEngine/)
  assert.match(main, /new DesktopApiClient/)
  assert.match(main, /fetchImpl:\s*net\.fetch/)
  assert.match(main, /app\.getPath\(['"]userData['"]\)/)
  assert.match(main, /app\.getVersion\(\)/)
  assert.match(main, /config\.releaseChannel/)
})

test('main navigation guard permits only fixed local application pages', () => {
  const mainSource = readFileSync(
    new URL('../src/main.mjs', import.meta.url),
    'utf8',
  )

  assert.match(mainSource, /resolveAppPage\(target, uiRoot\)/)
  assert.doesNotMatch(mainSource, /target\.startsWith\(['"]app:/)
})

test('folder actions are wired through Electron dialog and shell without renderer paths', () => {
  assert.match(main, /dialog\.showOpenDialog/)
  assert.match(main, /shell\.openPath/)
  assert.match(main, /assertSafeSyncRoot/)
  assert.match(main, /dirname\(process\.execPath\)/)
})

test('internal-test window title survives remote page title updates', () => {
  assert.match(main, /installEnvironmentTitleGuard/)
  assert.match(main, /config\.environmentLabel/)
})

test('desktop window merges native controls into the product top bar', () => {
  assert.match(main, /createIntegratedTitleBarOptions/)
  assert.match(main, /INTEGRATED_TITLE_BAR_CSS/)
  assert.match(main, /webContents\.insertCSS/)
  assert.match(main, /backgroundColor:\s*['"]#F8FBFF['"]/)
  assert.match(main, /app\.setAppUserModelId\(['"]com\.jiqing\.erp['"]\)/)
})

test('desktop installs a visible Windows business menu and native sync feedback', () => {
  assert.match(main, /createWindowsMenuTemplate/)
  assert.match(main, /Menu\.buildFromTemplate/)
  assert.doesNotMatch(main, /Menu\.setApplicationMenu\(null\)/)
  assert.match(main, /autoHideMenuBar:\s*false/)
  assert.match(main, /setMenuBarVisibility\(true\)/)
  assert.match(main, /setProgressBar/)
  assert.match(main, /new Notification/)
  assert.match(main, /emitWorkspaceCommand/)
  assert.match(main, /workspaceCommand/)
  assert.match(main, /window\.on\(['"]app-command['"]/)
})

test('desktop wires electron-updater through the bounded update controller', () => {
  assert.match(main, /electron-updater/)
  assert.match(main, /createDesktopUpdateController/)
  assert.match(main, /desktopUpdateController/)
  assert.match(main, /DESKTOP_IPC_CHANNELS\.updateState/)
  assert.match(main, /app\.isPackaged/)
})

test('enterprise splash stays visible until the loaded main window can replace it', () => {
  assert.match(main, /createEnterpriseSplashWindow/)
  assert.match(main, /closeEnterpriseSplashWindow/)
  assert.match(main, /session\.fromPartition\(SPLASH_PARTITION\)/)
  assert.match(
    main,
    /registerAppProtocol\(\s*splashSession\.protocol/,
  )
  assert.ok(
    main.indexOf('createEnterpriseSplashWindow')
      < main.indexOf('mainWindow = await createMainWindow()'),
  )
  assert.ok(
    main.indexOf('mainWindow = await createMainWindow()')
      < main.lastIndexOf('mainWindow.show()'),
  )
  assert.ok(
    main.lastIndexOf('mainWindow.show()')
      < main.lastIndexOf('closeEnterpriseSplashWindow'),
  )
})

test('desktop memory session is cleared when the application exits', () => {
  assert.match(main, /before-quit/)
  assert.match(main, /desktopIpcController\.clearSession\(\)/)
})

test('destroyed renderer is detached before sync session cleanup emits state', () => {
  assert.match(main, /hasLiveWindowWebContents/)
  assert.match(
    main,
    /if \(!hasLiveWindowWebContents\(window\)\) return/,
  )

  const destroyedHandler = main.slice(
    main.indexOf("window.webContents.once('destroyed'"),
    main.indexOf("window.on('closed'"),
  )
  assert.ok(
    destroyedHandler.indexOf('if (mainWindow === window) mainWindow = null')
      < destroyedHandler.indexOf('desktopIpcController.clearSession()'),
  )
})

test('successful web logout request clears the desktop memory session', () => {
  assert.match(main, /\/api\/auth\/logout/)
  assert.match(main, /webRequest\.onBeforeRequest/)
  assert.match(main, /desktopIpcController\.clearSession\(\)/)
})
