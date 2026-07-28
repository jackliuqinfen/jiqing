const moduleItems = Object.freeze([
  ['工作台', '/', 'CommandOrControl+1'],
  ['招投标', '/bidding', 'CommandOrControl+2'],
  ['项目管理', '/project-management', 'CommandOrControl+3'],
  ['资料中心', '/materials', 'CommandOrControl+4'],
  ['结算中心', '/finance', 'CommandOrControl+5'],
])

function action(callback, ...args) {
  return () => callback?.(...args)
}

function count(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : 0
}

export function createWindowsMenuTemplate({
  state = {},
  actions = {},
} = {}) {
  const hasFolder = typeof state.localRoot === 'string'
    && state.localRoot.trim().length > 0
  const canPause = ['checking_policy', 'syncing'].includes(state.status)

  return [
    {
      label: '模块',
      submenu: moduleItems.map(([label, path, accelerator]) => ({
        label,
        accelerator,
        click: action(actions.navigate, path),
      })),
    },
    {
      label: '导航',
      submenu: [
        {
          label: '返回',
          accelerator: 'Alt+Left',
          click: action(actions.dispatchWorkspaceCommand, 'workspace:back'),
        },
        {
          label: '前进',
          accelerator: 'Alt+Right',
          click: action(actions.dispatchWorkspaceCommand, 'workspace:forward'),
        },
        { type: 'separator' },
        {
          label: '全局搜索',
          accelerator: 'CommandOrControl+K',
          click: action(
            actions.dispatchWorkspaceCommand,
            'workspace:command-center',
          ),
        },
        {
          label: '恢复关闭的标签',
          accelerator: 'CommandOrControl+Shift+T',
          click: action(
            actions.dispatchWorkspaceCommand,
            'workspace:restore-closed-tab',
          ),
        },
      ],
    },
    {
      label: '资料',
      submenu: [
        {
          label: '本地资料同步设置',
          accelerator: 'CommandOrControl+Shift+S',
          click: action(actions.openSyncSettings),
        },
        { type: 'separator' },
        {
          label: '选择同步文件夹',
          click: action(actions.selectSyncFolder),
        },
        {
          label: '打开同步文件夹',
          accelerator: 'CommandOrControl+Shift+O',
          enabled: hasFolder,
          click: action(actions.openSyncFolder),
        },
        {
          label: '暂停同步',
          enabled: canPause,
          click: action(actions.pauseSync),
        },
        { type: 'separator' },
        {
          label: '退出',
          accelerator: 'Alt+F4',
          role: 'quit',
        },
      ],
    },
    {
      label: '查看',
      submenu: [
        { label: '刷新当前页面', accelerator: 'CommandOrControl+R', role: 'reload' },
        { type: 'separator' },
        { label: '恢复默认缩放', accelerator: 'CommandOrControl+0', role: 'resetZoom' },
        { label: '放大', accelerator: 'CommandOrControl+Plus', role: 'zoomIn' },
        { label: '缩小', accelerator: 'CommandOrControl+-', role: 'zoomOut' },
        { type: 'separator' },
        { label: '全屏', accelerator: 'F11', role: 'togglefullscreen' },
      ],
    },
    {
      label: '窗口',
      submenu: [
        { label: '最小化', role: 'minimize' },
        { label: '关闭窗口', accelerator: 'CommandOrControl+W', role: 'close' },
      ],
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '关于集庆工程管理',
          click: action(actions.showAbout),
        },
      ],
    },
  ]
}

export function syncPresentation(state = {}, previousStatus = '') {
  const completedFiles = count(state.completedFiles)
  const totalFiles = count(state.totalFiles)
  const failedFiles = count(state.failedFiles)
  const progress = totalFiles > 0
    ? Math.min(1, completedFiles / totalFiles)
    : 0

  if (state.status === 'syncing' || state.status === 'checking_policy') {
    return {
      progress: totalFiles > 0 ? progress : 2,
      progressMode: totalFiles > 0 ? 'normal' : 'indeterminate',
      notification: null,
    }
  }

  if (state.status === 'partial_failure') {
    return {
      progress,
      progressMode: 'error',
      notification: previousStatus === 'partial_failure'
        ? null
        : {
            title: '资料同步部分完成',
            body: `${completedFiles} 个文件已完成，${failedFiles} 个文件需要重试`,
          },
    }
  }

  if (state.status === 'completed') {
    return {
      progress: -1,
      progressMode: 'none',
      notification: previousStatus === 'completed'
        ? null
        : {
            title: '资料同步完成',
            body: `已同步 ${completedFiles} 个文件到本地资料文件夹`,
          },
    }
  }

  if (state.status === 'offline' && previousStatus !== 'offline') {
    return {
      progress: -1,
      progressMode: 'none',
      notification: {
        title: '资料同步已暂停',
        body: '当前无法连接服务器，恢复网络后可继续同步',
      },
    }
  }

  return {
    progress: -1,
    progressMode: 'none',
    notification: null,
  }
}
