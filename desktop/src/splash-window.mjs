export const SPLASH_URL = 'app://splash/'

export const SPLASH_PARTITION = 'desktop-erp-splash'

export function createSplashWindowOptions({ iconPath }) {
  if (typeof iconPath !== 'string' || iconPath.length === 0) {
    throw new Error('invalid splash icon path')
  }

  return Object.freeze({
    width: 680,
    height: 420,
    frame: false,
    show: false,
    center: true,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    autoHideMenuBar: true,
    backgroundColor: '#f5f8ff',
    icon: iconPath,
    webPreferences: Object.freeze({
      partition: SPLASH_PARTITION,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
    }),
  })
}

export async function createEnterpriseSplashWindow({
  BrowserWindow,
  iconPath,
}) {
  if (typeof BrowserWindow !== 'function') {
    throw new Error('invalid BrowserWindow constructor')
  }

  const window = new BrowserWindow(createSplashWindowOptions({ iconPath }))
  await window.loadURL(SPLASH_URL)
  if (!window.isDestroyed()) window.show()
  return window
}

export function closeEnterpriseSplashWindow(window) {
  if (!window || window.isDestroyed()) return false
  window.close()
  return true
}
