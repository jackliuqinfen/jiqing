export type WorkspaceTabKind = 'view' | 'project' | 'audit'

export type WorkspaceRouteInput = {
  path: string
  fullPath: string
  query: Record<string, unknown>
  metaTitle?: string
}

export type WorkspaceRouteDescriptor = {
  id: string
  kind: WorkspaceTabKind
  title: string
  icon: string
  closable: boolean
  pinned: boolean
}

export type WorkspaceTab = WorkspaceRouteDescriptor & {
  history: string[]
  historyIndex: number
  lastActivatedAt: number
}

export type WorkspaceState = {
  tabs: WorkspaceTab[]
  activeTabId: string
  recentlyClosed: WorkspaceTab[]
}

export type WorkspaceNavigationResult = {
  state: WorkspaceState
  route: string
}

const MAX_WORKSPACE_TABS = 12
const MAX_TAB_HISTORY = 30
const MAX_RECENTLY_CLOSED = 8

const projectViewMeta: Record<string, { title: string; icon: string }> = {
  ledger: { title: '项目台账', icon: 'task' },
  audit: { title: '审计联动', icon: 'view-module' },
  risk: { title: '风险项目', icon: 'error-circle' },
}

const auditViewMeta: Record<string, { title: string; icon: string }> = {
  kanban: { title: '审计看板', icon: 'view-module' },
  table: { title: '审计台账', icon: 'list' },
  gantt: { title: '审计排期', icon: 'calendar' },
}

const financeViewMeta: Record<string, { title: string; icon: string }> = {
  boss: { title: '结算总览', icon: 'dashboard' },
  workbench: { title: '财务工作台', icon: 'list' },
  ledger: { title: '项目结算台账', icon: 'file-paste' },
  invoice: { title: '发票管理', icon: 'file-paste' },
  payment: { title: '收付款管理', icon: 'list' },
  documents: { title: '结算资料', icon: 'folder' },
  retention: { title: '质保金管理', icon: 'folder' },
}

function queryText(query: Record<string, unknown>, key: string) {
  const value = query[key]
  return typeof value === 'string' ? value.trim() : ''
}

export function createWorkspaceState(): WorkspaceState {
  return { tabs: [], activeTabId: '', recentlyClosed: [] }
}

export function deriveWorkspaceRoute(route: WorkspaceRouteInput): WorkspaceRouteDescriptor {
  if (route.path === '/') {
    return {
      id: 'view:/:overview',
      kind: 'view',
      title: '工作台',
      icon: 'dashboard',
      closable: false,
      pinned: true,
    }
  }

  if (route.path === '/project-management') {
    const projectId = queryText(route.query, 'projectId')
    if (projectId) {
      return {
        id: `project:${projectId}`,
        kind: 'project',
        title: queryText(route.query, 'projectName') || '项目详情',
        icon: 'task',
        closable: true,
        pinned: false,
      }
    }
    const view = queryText(route.query, 'view') || 'ledger'
    const meta = projectViewMeta[view] || projectViewMeta.ledger
    return {
      id: `view:/project-management:${view}`,
      kind: 'view',
      title: meta.title,
      icon: meta.icon,
      closable: true,
      pinned: false,
    }
  }

  if (route.path === '/audit') {
    const projectId = queryText(route.query, 'projectId')
    if (projectId) {
      return {
        id: `audit:${projectId}`,
        kind: 'audit',
        title: queryText(route.query, 'projectName') || '审计详情',
        icon: 'view-module',
        closable: true,
        pinned: false,
      }
    }
    const view = queryText(route.query, 'mode') || 'kanban'
    const meta = auditViewMeta[view] || auditViewMeta.kanban
    return {
      id: `view:/audit:${view}`,
      kind: 'view',
      title: meta.title,
      icon: meta.icon,
      closable: true,
      pinned: false,
    }
  }

  if (route.path === '/materials') {
    return {
      id: 'view:/materials:library',
      kind: 'view',
      title: '资料中心',
      icon: 'folder',
      closable: true,
      pinned: false,
    }
  }

  if (route.path === '/finance') {
    const view = queryText(route.query, 'view') || 'boss'
    const meta = financeViewMeta[view] || financeViewMeta.boss
    return {
      id: `view:/finance:${view}`,
      kind: 'view',
      title: meta.title,
      icon: meta.icon,
      closable: true,
      pinned: false,
    }
  }

  const view = queryText(route.query, 'view') || 'overview'
  return {
    id: `view:${route.path}:${view}`,
    kind: 'view',
    title: route.metaTitle || '业务页面',
    icon: 'list',
    closable: true,
    pinned: false,
  }
}

function cloneState(state: WorkspaceState): WorkspaceState {
  return {
    activeTabId: state.activeTabId,
    tabs: state.tabs.map((tab) => ({
      ...tab,
      history: [...tab.history],
    })),
    recentlyClosed: (state.recentlyClosed || []).map((tab) => ({
      ...tab,
      history: [...tab.history],
    })),
  }
}

function trimTabs(state: WorkspaceState) {
  while (state.tabs.length > MAX_WORKSPACE_TABS) {
    const removable = state.tabs
      .filter((tab) => !tab.pinned && tab.id !== state.activeTabId)
      .sort((left, right) => left.lastActivatedAt - right.lastActivatedAt)[0]
    if (!removable) break
    state.tabs = state.tabs.filter((tab) => tab.id !== removable.id)
  }
}

export function recordWorkspaceRoute(
  current: WorkspaceState,
  route: WorkspaceRouteInput,
  now = Date.now(),
): WorkspaceState {
  const state = cloneState(current)
  const descriptor = deriveWorkspaceRoute(route)
  const existing = state.tabs.find((tab) => tab.id === descriptor.id)

  if (!existing) {
    state.tabs.push({
      ...descriptor,
      history: [route.fullPath],
      historyIndex: 0,
      lastActivatedAt: now,
    })
  } else {
    existing.title = descriptor.title === '项目详情' && existing.title !== '项目详情'
      ? existing.title
      : descriptor.title
    existing.icon = descriptor.icon
    existing.lastActivatedAt = now
    const currentRoute = existing.history[existing.historyIndex]
    if (currentRoute !== route.fullPath) {
      const knownIndex = existing.history.indexOf(route.fullPath)
      if (knownIndex >= 0) {
        existing.historyIndex = knownIndex
      } else {
        existing.history = [
          ...existing.history.slice(0, existing.historyIndex + 1),
          route.fullPath,
        ].slice(-MAX_TAB_HISTORY)
        existing.historyIndex = existing.history.length - 1
      }
    }
  }

  state.activeTabId = descriptor.id
  trimTabs(state)
  return state
}

export function activateWorkspaceTab(
  current: WorkspaceState,
  tabId: string,
  now = Date.now(),
): WorkspaceNavigationResult {
  const state = cloneState(current)
  const tab = state.tabs.find((item) => item.id === tabId)
  if (!tab) return { state, route: '' }
  tab.lastActivatedAt = now
  state.activeTabId = tab.id
  return { state, route: tab.history[tab.historyIndex] || '' }
}

export function closeWorkspaceTab(
  current: WorkspaceState,
  tabId: string,
): WorkspaceNavigationResult & { closed: boolean } {
  const state = cloneState(current)
  const index = state.tabs.findIndex((item) => item.id === tabId)
  if (index < 0 || !state.tabs[index].closable || state.tabs[index].pinned) {
    return { state, route: '', closed: false }
  }

  const wasActive = state.activeTabId === tabId
  const [closedTab] = state.tabs.splice(index, 1)
  state.recentlyClosed = [closedTab, ...state.recentlyClosed.filter((tab) => tab.id !== closedTab.id)]
    .slice(0, MAX_RECENTLY_CLOSED)
  if (!wasActive) return { state, route: '', closed: true }

  const nextTab = state.tabs[Math.min(index, state.tabs.length - 1)]
  state.activeTabId = nextTab?.id || ''
  return {
    state,
    route: nextTab?.history[nextTab.historyIndex] || '/',
    closed: true,
  }
}

export function closeOtherWorkspaceTabs(
  current: WorkspaceState,
  tabId: string,
): WorkspaceState {
  const state = cloneState(current)
  const keep = state.tabs.find((tab) => tab.id === tabId)
  if (!keep) return state
  const closing = state.tabs.filter((tab) => tab.id !== tabId && !tab.pinned)
  state.recentlyClosed = [
    ...closing.reverse(),
    ...state.recentlyClosed,
  ]
    .filter((tab, index, tabs) => tabs.findIndex((item) => item.id === tab.id) === index)
    .slice(0, MAX_RECENTLY_CLOSED)
  state.tabs = state.tabs.filter((tab) => tab.id === tabId || tab.pinned)
  state.activeTabId = tabId
  return state
}

export function navigateWorkspaceHistory(
  current: WorkspaceState,
  direction: -1 | 1,
): WorkspaceNavigationResult {
  const state = cloneState(current)
  const tab = state.tabs.find((item) => item.id === state.activeTabId)
  if (!tab) return { state, route: '' }
  const nextIndex = tab.historyIndex + direction
  if (nextIndex < 0 || nextIndex >= tab.history.length) return { state, route: '' }
  tab.historyIndex = nextIndex
  tab.lastActivatedAt = Date.now()
  return { state, route: tab.history[nextIndex] || '' }
}

export function setWorkspaceTabPinned(
  current: WorkspaceState,
  tabId: string,
  pinned: boolean,
): WorkspaceState {
  const state = cloneState(current)
  const tab = state.tabs.find((item) => item.id === tabId)
  if (!tab) return state
  tab.pinned = pinned
  tab.closable = !pinned
  return state
}

export function reorderWorkspaceTab(
  current: WorkspaceState,
  tabId: string,
  targetIndex: number,
): WorkspaceState {
  const state = cloneState(current)
  const currentIndex = state.tabs.findIndex((tab) => tab.id === tabId)
  if (currentIndex < 0) return state
  const boundedIndex = Math.max(0, Math.min(targetIndex, state.tabs.length - 1))
  const [tab] = state.tabs.splice(currentIndex, 1)
  state.tabs.splice(boundedIndex, 0, tab)
  return state
}

export function restoreLastClosedWorkspaceTab(
  current: WorkspaceState,
): WorkspaceNavigationResult {
  const state = cloneState(current)
  const tab = state.recentlyClosed.shift()
  if (!tab) return { state, route: '' }
  const existing = state.tabs.find((item) => item.id === tab.id)
  if (!existing) state.tabs.push(tab)
  state.activeTabId = tab.id
  trimTabs(state)
  return {
    state,
    route: tab.history[tab.historyIndex] || '',
  }
}

export function restoreWorkspaceState(raw: string | null): WorkspaceState {
  if (!raw) return createWorkspaceState()
  try {
    const parsed = JSON.parse(raw) as Partial<WorkspaceState>
    if (!Array.isArray(parsed.tabs)) return createWorkspaceState()
    const tabs = parsed.tabs
      .filter((tab): tab is WorkspaceTab => (
        Boolean(tab)
        && typeof tab.id === 'string'
        && typeof tab.title === 'string'
        && Array.isArray(tab.history)
        && tab.history.every((route) => typeof route === 'string')
      ))
      .slice(0, MAX_WORKSPACE_TABS)
      .map((tab) => ({
        ...tab,
        history: tab.history.slice(-MAX_TAB_HISTORY),
        historyIndex: Math.max(0, Math.min(Number(tab.historyIndex || 0), tab.history.length - 1)),
        lastActivatedAt: Number(tab.lastActivatedAt || 0),
      }))
    const activeTabId = tabs.some((tab) => tab.id === parsed.activeTabId)
      ? String(parsed.activeTabId)
      : tabs[0]?.id || ''
    const recentlyClosed = Array.isArray(parsed.recentlyClosed)
      ? parsed.recentlyClosed
        .filter((tab): tab is WorkspaceTab => (
          Boolean(tab)
          && typeof tab.id === 'string'
          && typeof tab.title === 'string'
          && Array.isArray(tab.history)
        ))
        .slice(0, MAX_RECENTLY_CLOSED)
        .map((tab) => ({ ...tab, history: [...tab.history] }))
      : []
    return { tabs, activeTabId, recentlyClosed }
  } catch {
    return createWorkspaceState()
  }
}
