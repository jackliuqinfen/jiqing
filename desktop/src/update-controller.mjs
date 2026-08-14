const BUSY_STATUSES = new Set([
  'checking',
  'available',
  'downloading',
  'downloaded',
])

function publicState(state) {
  return Object.freeze({ ...state })
}

function boundedVersion(value) {
  return typeof value === 'string' && value.length <= 64 ? value : ''
}

function boundedProgress(value) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value)))
}

export function createDesktopUpdateController({
  currentVersion,
  enabled,
  updater,
  emitState = () => {},
  now = () => new Date().toISOString(),
}) {
  if (!updater || typeof updater.on !== 'function') {
    throw new Error('invalid desktop updater')
  }

  let state = enabled
    ? {
        status: 'idle',
        currentVersion,
        availableVersion: '',
        progressPercent: 0,
        canCheck: true,
        canInstall: false,
        lastCheckedAt: '',
        message: '可检查是否有新的客户端版本',
      }
    : {
        status: 'unavailable',
        currentVersion,
        availableVersion: '',
        progressPercent: 0,
        canCheck: false,
        canInstall: false,
        lastCheckedAt: '',
        message: '在线更新仅在已安装的 Windows 客户端中可用',
      }

  const publish = (patch) => {
    state = { ...state, ...patch }
    const result = publicState(state)
    emitState(result)
    return result
  }

  if (enabled) {
    updater.autoDownload = true
    updater.autoInstallOnAppQuit = true

    updater.on('checking-for-update', () => {
      publish({
        status: 'checking',
        canCheck: false,
        canInstall: false,
        progressPercent: 0,
        message: '正在检查新版本',
      })
    })
    updater.on('update-available', (info = {}) => {
      const availableVersion = boundedVersion(info.version)
      publish({
        status: 'available',
        availableVersion,
        canCheck: false,
        canInstall: false,
        lastCheckedAt: now(),
        message: availableVersion
          ? `发现新版本 ${availableVersion}，正在下载`
          : '发现新版本，正在下载',
      })
    })
    updater.on('download-progress', (progress = {}) => {
      publish({
        status: 'downloading',
        progressPercent: boundedProgress(progress.percent),
        canCheck: false,
        canInstall: false,
        message: '正在下载更新',
      })
    })
    updater.on('update-downloaded', (info = {}) => {
      const availableVersion = boundedVersion(info.version) || state.availableVersion
      publish({
        status: 'downloaded',
        availableVersion,
        progressPercent: 100,
        canCheck: false,
        canInstall: true,
        lastCheckedAt: state.lastCheckedAt || now(),
        message: '更新已下载，可立即重启安装',
      })
    })
    updater.on('update-not-available', () => {
      publish({
        status: 'up_to_date',
        availableVersion: '',
        progressPercent: 0,
        canCheck: true,
        canInstall: false,
        lastCheckedAt: now(),
        message: '当前已是最新版本',
      })
    })
    updater.on('error', () => {
      publish({
        status: 'error',
        canCheck: true,
        canInstall: false,
        lastCheckedAt: now(),
        message: '检查更新失败，请确认网络后重试',
      })
    })
  }

  return Object.freeze({
    getState() {
      return publicState(state)
    },
    async check() {
      if (!enabled) throw new Error('desktop update unavailable')
      if (BUSY_STATUSES.has(state.status)) {
        throw new Error('desktop update already in progress')
      }
      publish({
        status: 'checking',
        canCheck: false,
        canInstall: false,
        progressPercent: 0,
        message: '正在检查新版本',
      })
      try {
        await updater.checkForUpdates()
      } catch (error) {
        publish({
          status: 'error',
          canCheck: true,
          canInstall: false,
          lastCheckedAt: now(),
          message: '检查更新失败，请确认网络后重试',
        })
        throw error
      }
      return publicState(state)
    },
    install() {
      if (state.status !== 'downloaded' || !state.canInstall) {
        throw new Error('desktop update is not ready to install')
      }
      updater.quitAndInstall(false, true)
    },
  })
}
