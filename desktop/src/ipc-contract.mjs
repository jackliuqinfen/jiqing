import { assertTrustedSender } from './security.mjs'

export const DESKTOP_IPC_CHANNELS = Object.freeze({
  getCapabilities: 'desktop:get-capabilities',
  selectSyncFolder: 'desktop:select-sync-folder',
  getSyncState: 'desktop:get-sync-state',
  startSync: 'desktop:start-sync',
  pauseSync: 'desktop:pause-sync',
  openSyncFolder: 'desktop:open-sync-folder',
  getUpdateState: 'desktop:get-update-state',
  checkForUpdates: 'desktop:check-for-updates',
  installUpdate: 'desktop:install-update',
  syncState: 'desktop:sync-state',
  updateState: 'desktop:update-state',
  workspaceCommand: 'desktop:workspace-command',
})

const PROJECT_REF_PATTERN = /^(project|audit):[A-Za-z0-9-]+$/
const START_REQUEST_KEYS = Object.freeze([
  'authToken',
  'projectRefs',
  'userId',
])

function isPlainObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

function hasExactKeys(value, expectedKeys) {
  const keys = Object.keys(value).sort()
  return (
    keys.length === expectedKeys.length
    && keys.every((key, index) => key === expectedKeys[index])
  )
}

function isBoundedNonBlankString(value, maximumLength) {
  return (
    typeof value === 'string'
    && value.length <= maximumLength
    && value.trim().length > 0
  )
}

function validateProjectRefs(value) {
  if (!Array.isArray(value) || value.length > 500) {
    throw new Error('invalid project refs')
  }
  const seen = new Set()
  for (const reference of value) {
    if (
      typeof reference !== 'string'
      || !PROJECT_REF_PATTERN.test(reference)
      || seen.has(reference)
    ) {
      throw new Error('invalid project refs')
    }
    seen.add(reference)
  }
  return Object.freeze([...value])
}

export function validateSyncStartRequest(value) {
  if (!isPlainObject(value) || !hasExactKeys(value, START_REQUEST_KEYS)) {
    throw new Error('invalid sync start request')
  }
  if (!isBoundedNonBlankString(value.authToken, 8192)) {
    throw new Error('invalid auth token')
  }
  if (!isBoundedNonBlankString(value.userId, 128)) {
    throw new Error('invalid user id')
  }

  return Object.freeze({
    authToken: value.authToken,
    userId: value.userId,
    projectRefs: validateProjectRefs(value.projectRefs),
  })
}

function createInitialState() {
  return {
    status: 'paused',
    localRoot: '',
    selectedProjectRefs: [],
    completedFiles: 0,
    totalFiles: 0,
    failedFiles: 0,
    bytesDownloaded: 0,
    lastSuccessAt: '',
    message: '本地同步尚未启动，未下载任何文件',
  }
}

function publicState(state) {
  return Object.freeze({
    ...state,
    selectedProjectRefs: Object.freeze([...state.selectedProjectRefs]),
  })
}

export function createDesktopIpcController({ syncEngine = null } = {}) {
  if (syncEngine) {
    return Object.freeze({
      getState() {
        return syncEngine.getState()
      },
      hasActiveSession() {
        return syncEngine.hasActiveSession()
      },
      setLocalRoot(localRoot) {
        if (!isBoundedNonBlankString(localRoot, 32767)) {
          throw new Error('invalid local sync root')
        }
        return syncEngine.setLocalRoot(localRoot)
      },
      setSelectedProjectRefs(projectRefs) {
        return syncEngine.setSelectedProjectRefs(validateProjectRefs(projectRefs))
      },
      start(value) {
        return syncEngine.start(validateSyncStartRequest(value))
      },
      pause() {
        return syncEngine.pause()
      },
      clearSession() {
        syncEngine.clearSession()
      },
    })
  }

  let privateSession = null
  let state = createInitialState()

  return Object.freeze({
    getState() {
      return publicState(state)
    },
    hasActiveSession() {
      return privateSession !== null
    },
    setLocalRoot(localRoot) {
      if (!isBoundedNonBlankString(localRoot, 32767)) {
        throw new Error('invalid local sync root')
      }
      state = {
        ...state,
        localRoot,
        message: '已选择本地资料文件夹，尚未开始下载',
      }
      return publicState(state)
    },
    setSelectedProjectRefs(projectRefs) {
      state = {
        ...state,
        selectedProjectRefs: [...validateProjectRefs(projectRefs)],
      }
      return publicState(state)
    },
    start(value) {
      const request = validateSyncStartRequest(value)
      privateSession = {
        authToken: request.authToken,
        userId: request.userId,
      }
      state = {
        ...state,
        status: 'checking_policy',
        selectedProjectRefs: [...request.projectRefs],
        completedFiles: 0,
        totalFiles: 0,
        failedFiles: 0,
        bytesDownloaded: 0,
        lastSuccessAt: '',
        message: '正在等待同步策略检查；同步引擎尚未接入，未下载任何文件',
      }
      return publicState(state)
    },
    pause() {
      privateSession = null
      state = {
        ...state,
        status: 'paused',
        message: '本地同步已暂停，登录凭证已从桌面内存清除',
      }
      return publicState(state)
    },
    clearSession() {
      const localRoot = state.localRoot
      privateSession = null
      state = {
        ...createInitialState(),
        localRoot,
        message: '桌面同步会话已清除',
      }
    },
  })
}

function assertNoArguments(args) {
  if (args.length !== 0) throw new Error('unexpected ipc arguments')
}

function assertOneArgument(args) {
  if (args.length !== 1) throw new Error('invalid ipc arguments')
  return args[0]
}

export function registerDesktopIpcHandlers({
  ipcMain,
  allowedOrigin,
  appVersion,
  releaseChannel,
  controller,
  updateController = null,
  selectFolder,
  openFolder,
  emitState = () => {},
  syncScheduler = null,
  onSyncStart = () => {},
}) {
  if (!ipcMain || typeof ipcMain.handle !== 'function') {
    throw new Error('invalid ipc main')
  }

  const handle = (channel, callback) => {
    ipcMain.handle(channel, async (event, ...args) => {
      assertTrustedSender(event?.senderFrame?.url || '', allowedOrigin)
      return callback(args)
    })
  }
  const emit = (state) => {
    emitState(state)
    return state
  }

  handle(DESKTOP_IPC_CHANNELS.getCapabilities, async (args) => {
    assertNoArguments(args)
    return Object.freeze({
      desktop: true,
      protocolVersion: 1,
      clientVersion: appVersion,
      releaseChannel,
    })
  })
  handle(DESKTOP_IPC_CHANNELS.selectSyncFolder, async (args) => {
    assertNoArguments(args)
    const selected = await selectFolder()
    if (selected === '') return ''
    if (!isBoundedNonBlankString(selected, 32767)) {
      throw new Error('invalid selected sync folder')
    }
    emit(controller.setLocalRoot(selected))
    return selected
  })
  handle(DESKTOP_IPC_CHANNELS.getSyncState, async (args) => {
    assertNoArguments(args)
    return controller.getState()
  })
  handle(DESKTOP_IPC_CHANNELS.startSync, async (args) => {
    const request = assertOneArgument(args)
    const validatedRequest = validateSyncStartRequest(request)
    onSyncStart(validatedRequest)
    const result = await controller.start(validatedRequest)
    if (syncScheduler) syncScheduler.arm(validatedRequest, result)
    return emit(result)
  })
  handle(DESKTOP_IPC_CHANNELS.pauseSync, async (args) => {
    assertNoArguments(args)
    if (syncScheduler) syncScheduler.stop()
    return emit(await controller.pause())
  })
  handle(DESKTOP_IPC_CHANNELS.openSyncFolder, async (args) => {
    assertNoArguments(args)
    const localRoot = controller.getState().localRoot
    if (!localRoot) throw new Error('sync folder is not selected')
    await openFolder(localRoot)
  })
  handle(DESKTOP_IPC_CHANNELS.getUpdateState, async (args) => {
    assertNoArguments(args)
    if (!updateController) throw new Error('desktop update unavailable')
    return updateController.getState()
  })
  handle(DESKTOP_IPC_CHANNELS.checkForUpdates, async (args) => {
    assertNoArguments(args)
    if (!updateController) throw new Error('desktop update unavailable')
    return updateController.check()
  })
  handle(DESKTOP_IPC_CHANNELS.installUpdate, async (args) => {
    assertNoArguments(args)
    if (!updateController) throw new Error('desktop update unavailable')
    updateController.install()
  })
}
