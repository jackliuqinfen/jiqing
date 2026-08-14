import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createWindowsMenuTemplate,
  syncPresentation,
} from '../src/windows-integration.mjs'

function flattenMenu(template) {
  return template.flatMap((group) => group.submenu || [])
}

test('Windows menu exposes business navigation and local material sync actions', () => {
  const calls = []
  const template = createWindowsMenuTemplate({
    state: {
      status: 'syncing',
      localRoot: 'C:\\ERP资料',
      completedFiles: 3,
      totalFiles: 10,
      failedFiles: 0,
    },
    actions: {
      navigate: (path) => calls.push(['navigate', path]),
      dispatchWorkspaceCommand: (command) => calls.push(['workspace', command]),
      openSyncSettings: () => calls.push(['sync-settings']),
      selectSyncFolder: () => calls.push(['select-folder']),
      openSyncFolder: () => calls.push(['open-folder']),
      pauseSync: () => calls.push(['pause']),
      showAbout: () => calls.push(['about']),
    },
  })

  assert.deepEqual(
    template.map((group) => group.label),
    ['模块', '导航', '资料', '查看', '窗口', '帮助'],
  )

  const items = flattenMenu(template)
  const labels = items.map((item) => item.label).filter(Boolean)
  for (const label of [
    '工作台',
    '招投标',
    '项目管理',
    '资料中心',
    '结算中心',
    '返回',
    '前进',
    '全局搜索',
    '恢复关闭的标签',
    '本地资料同步设置',
    '选择同步文件夹',
    '打开同步文件夹',
    '暂停同步',
    '关于集庆工程管理',
  ]) {
    assert.ok(labels.includes(label), `missing menu item: ${label}`)
  }

  items.find((item) => item.label === '项目管理').click()
  items.find((item) => item.label === '全局搜索').click()
  items.find((item) => item.label === '本地资料同步设置').click()
  items.find((item) => item.label === '暂停同步').click()

  assert.deepEqual(calls, [
    ['navigate', '/project-management'],
    ['workspace', 'workspace:command-center'],
    ['sync-settings'],
    ['pause'],
  ])
})

test('Windows menu disables folder operations until they are valid', () => {
  const template = createWindowsMenuTemplate({
    state: {
      status: 'paused',
      localRoot: '',
      completedFiles: 0,
      totalFiles: 0,
      failedFiles: 0,
    },
    actions: {},
  })
  const items = flattenMenu(template)

  assert.equal(
    items.find((item) => item.label === '打开同步文件夹').enabled,
    false,
  )
  assert.equal(
    items.find((item) => item.label === '暂停同步').enabled,
    false,
  )
})

test('sync presentation maps progress and completion to native Windows feedback', () => {
  assert.deepEqual(
    syncPresentation({
      status: 'syncing',
      completedFiles: 4,
      totalFiles: 10,
      failedFiles: 0,
    }),
    {
      progress: 0.4,
      progressMode: 'normal',
      notification: null,
    },
  )

  assert.deepEqual(
    syncPresentation({
      status: 'completed',
      completedFiles: 10,
      totalFiles: 10,
      failedFiles: 0,
    }, 'syncing'),
    {
      progress: -1,
      progressMode: 'none',
      notification: {
        title: '资料同步完成',
        body: '已同步 10 个文件到本地资料文件夹',
      },
    },
  )

  assert.deepEqual(
    syncPresentation({
      status: 'partial_failure',
      completedFiles: 8,
      totalFiles: 10,
      failedFiles: 2,
    }, 'syncing'),
    {
      progress: 0.8,
      progressMode: 'error',
      notification: {
        title: '资料同步部分完成',
        body: '8 个文件已完成，2 个文件需要重试',
      },
    },
  )
})
