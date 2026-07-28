import assert from 'node:assert/strict'
import test from 'node:test'

import {
  activateWorkspaceTab,
  closeWorkspaceTab,
  createWorkspaceState,
  deriveWorkspaceRoute,
  navigateWorkspaceHistory,
  recordWorkspaceRoute,
  reorderWorkspaceTab,
  restoreLastClosedWorkspaceTab,
} from '../src/workspace/workspaceTabs.ts'

test('project routes create independent object tabs while list routes reuse their view tab', () => {
  let state = createWorkspaceState()
  state = recordWorkspaceRoute(state, {
    path: '/project-management',
    fullPath: '/project-management?view=ledger',
    query: { view: 'ledger' },
    metaTitle: '项目管理',
  })
  state = recordWorkspaceRoute(state, {
    path: '/project-management',
    fullPath: '/project-management?projectId=p-1&projectName=一号项目',
    query: { projectId: 'p-1', projectName: '一号项目' },
    metaTitle: '项目管理',
  })
  state = recordWorkspaceRoute(state, {
    path: '/project-management',
    fullPath: '/project-management?projectId=p-2&projectName=二号项目',
    query: { projectId: 'p-2', projectName: '二号项目' },
    metaTitle: '项目管理',
  })

  assert.deepEqual(state.tabs.map((tab) => tab.id), [
    'view:/project-management:ledger',
    'project:p-1',
    'project:p-2',
  ])
  assert.equal(state.tabs[1].title, '一号项目')
  assert.equal(state.activeTabId, 'project:p-2')
})

test('same workspace tab keeps bounded navigation history and supports back and forward', () => {
  let state = createWorkspaceState()
  state = recordWorkspaceRoute(state, {
    path: '/materials',
    fullPath: '/materials?view=library',
    query: { view: 'library' },
    metaTitle: '资料中心',
  })
  state = recordWorkspaceRoute(state, {
    path: '/materials',
    fullPath: '/materials?view=library&fileType=pdf',
    query: { view: 'library', fileType: 'pdf' },
    metaTitle: '资料中心',
  })

  const back = navigateWorkspaceHistory(state, -1)
  assert.equal(back.route, '/materials?view=library')
  assert.equal(back.state.tabs[0].historyIndex, 0)

  const forward = navigateWorkspaceHistory(back.state, 1)
  assert.equal(forward.route, '/materials?view=library&fileType=pdf')
  assert.equal(forward.state.tabs[0].historyIndex, 1)
})

test('closing the active tab activates the adjacent tab and pinned tabs cannot close', () => {
  let state = createWorkspaceState()
  state = recordWorkspaceRoute(state, {
    path: '/',
    fullPath: '/',
    query: {},
    metaTitle: '工作台',
  })
  state = recordWorkspaceRoute(state, {
    path: '/project-management',
    fullPath: '/project-management?projectId=p-1&projectName=一号项目',
    query: { projectId: 'p-1', projectName: '一号项目' },
    metaTitle: '项目管理',
  })

  const closed = closeWorkspaceTab(state, 'project:p-1')
  assert.equal(closed.route, '/')
  assert.equal(closed.state.activeTabId, 'view:/:overview')
  assert.equal(closed.state.tabs.length, 1)

  const pinnedClose = closeWorkspaceTab(closed.state, 'view:/:overview')
  assert.equal(pinnedClose.state.tabs.length, 1)
  assert.equal(pinnedClose.closed, false)
})

test('activating a tab returns its current route without adding history', () => {
  let state = createWorkspaceState()
  state = recordWorkspaceRoute(state, {
    path: '/project-management',
    fullPath: '/project-management?view=ledger',
    query: { view: 'ledger' },
    metaTitle: '项目管理',
  })
  state = recordWorkspaceRoute(state, {
    path: '/project-management',
    fullPath: '/project-management?projectId=p-1&projectName=一号项目',
    query: { projectId: 'p-1', projectName: '一号项目' },
    metaTitle: '项目管理',
  })

  const activated = activateWorkspaceTab(state, 'view:/project-management:ledger')
  assert.equal(activated.route, '/project-management?view=ledger')
  assert.equal(activated.state.tabs[0].history.length, 1)
})

test('route derivation creates stable ids for core views and object details', () => {
  assert.deepEqual(
    deriveWorkspaceRoute({
      path: '/project-management',
      fullPath: '/project-management?view=audit',
      query: { view: 'audit' },
      metaTitle: '项目管理',
    }),
    {
      id: 'view:/project-management:audit',
      kind: 'view',
      title: '审计联动',
      icon: 'view-module',
      closable: true,
      pinned: false,
    },
  )

  assert.equal(
    deriveWorkspaceRoute({
      path: '/project-management',
      fullPath: '/project-management?projectId=p-1',
      query: { projectId: 'p-1' },
      metaTitle: '项目管理',
    }).id,
    'project:p-1',
  )
})

test('closed tabs can be restored and tabs can be reordered without losing history', () => {
  let state = createWorkspaceState()
  state = recordWorkspaceRoute(state, {
    path: '/project-management',
    fullPath: '/project-management?view=ledger',
    query: { view: 'ledger' },
    metaTitle: '项目管理',
  })
  state = recordWorkspaceRoute(state, {
    path: '/materials',
    fullPath: '/materials?view=library',
    query: { view: 'library' },
    metaTitle: '资料中心',
  })

  const closed = closeWorkspaceTab(state, 'view:/materials:library')
  assert.equal(closed.state.recentlyClosed.length, 1)
  const restored = restoreLastClosedWorkspaceTab(closed.state)
  assert.equal(restored.route, '/materials?view=library')
  assert.equal(restored.state.activeTabId, 'view:/materials:library')

  const reordered = reorderWorkspaceTab(restored.state, 'view:/materials:library', 0)
  assert.equal(reordered.tabs[0].id, 'view:/materials:library')
  assert.deepEqual(reordered.tabs[0].history, ['/materials?view=library'])
})
