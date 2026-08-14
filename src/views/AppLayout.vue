<template>
  <div
    class="system-shell"
    :class="[`system-shell--${sidebarMode}`, { 'system-shell--resizing': resizing }]"
    :style="shellStyle"
  >
    <button v-if="sidebarMode === 'hidden'" type="button" class="sidebar-restore" @click="setSidebarMode('full')">
      <AIcon name="list" />
      <span>展开导航</span>
    </button>

    <header class="platform-topbar">
      <router-link to="/" class="topbar-brand" aria-label="江苏集庆建设">
        <img :src="brandLogo" alt="" />
      </router-link>
      <nav class="platform-nav" aria-label="平台级模块">
        <router-link
          v-for="item in orderedMainNav"
          :key="item.path"
          :to="item.path"
          class="platform-link"
          :class="{ 'platform-link--active': isTopNavActive(item.path), 'platform-link--draggable': canReorderModules, 'platform-link--dragging': draggedModulePath === item.path }"
          :aria-current="isTopNavActive(item.path) ? 'page' : undefined"
          :draggable="canReorderModules"
          :title="getModuleTitle(item)"
          @dragstart="startModuleDrag(item.path, $event)"
          @dragover.prevent="dragOverModule(item.path)"
          @drop.prevent="dropModule(item.path)"
          @dragend="finishModuleDrag"
        >
          <AIcon :name="item.icon" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="topbar-actions">
        <button type="button" class="topbar-command-trigger" title="全局搜索与命令 (Ctrl+K)" @click="commandCenterVisible = true">
          <AIcon name="search" />
          <span>搜索</span>
          <kbd>Ctrl K</kbd>
        </button>
        <button v-if="sidebarMode === 'hidden'" type="button" class="topbar-icon-button" title="展开左侧导航" @click="setSidebarMode('full')">
          <AIcon name="list" />
        </button>
        <router-link
          v-if="authStore.isAuthenticated"
          to="/settings"
          class="topbar-user"
          :title="`个人设置 · 当前登录用户：${userDisplayName}`"
        >
          <span class="topbar-user__avatar" aria-hidden="true">
            <img v-if="userAvatarUrl" :src="userAvatarUrl" alt="" />
            <span v-else>{{ userInitial }}</span>
          </span>
          <span class="topbar-user__copy">
            <small>欢迎回来</small>
            <strong>{{ userDisplayName }}</strong>
          </span>
        </router-link>
        <router-link v-if="authStore.isAdmin" to="/admin/field-configs" class="topbar-action-link">
          <AIcon name="setting" />
          <span>后台管理</span>
        </router-link>
        <button v-if="authStore.isAuthenticated" type="button" class="topbar-action-link" @click="logout">
          <AIcon name="rollback" />
          <span>退出</span>
        </button>
        <button v-else type="button" class="topbar-action-link topbar-action-link--primary" @click="router.push('/login')">
          <AIcon name="user" />
          <span>登录</span>
        </button>
      </div>
    </header>

    <aside v-if="sidebarMode !== 'hidden'" class="system-sidebar">
      <nav class="module-nav" aria-label="当前模块业务功能">
        <div class="sidebar-module-heading" :title="activeModule?.label || '工作台'">
          <span class="sidebar-module-heading__icon"><AIcon :name="activeModule?.icon || 'dashboard'" /></span>
          <strong>{{ activeModule?.label || '工作台' }}</strong>
          <span class="sidebar-module-caret" aria-hidden="true" />
        </div>
        <div class="sidebar-module-items">
          <router-link
            v-for="item in currentSideNav"
            :key="item.key"
            :to="sideNavTarget(item)"
            class="module-link"
            :class="{ 'module-link--active': isSideNavActive(item), 'module-link--disabled': item.disabled }"
            :aria-current="isSideNavActive(item) ? 'page' : undefined"
            :title="item.description || item.label"
            @click="handleSideNavClick(item, $event)"
          >
            <span class="module-link__icon"><AIcon :name="item.icon" /></span>
            <span>{{ item.label }}</span>
            <small v-if="item.badge">{{ item.badge }}</small>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-foot">
        <button
          type="button"
          class="sidebar-collapse-toggle"
          :title="sidebarMode === 'full' ? '收起侧边栏' : '展开侧边栏'"
          @click="toggleSidebarMode"
        >
          <AIcon :name="sidebarMode === 'full' ? 'menu-fold' : 'menu-unfold'" />
          <span>{{ sidebarMode === 'full' ? '收起' : '展开' }}</span>
        </button>
      </div>
      <button
        type="button"
        class="sidebar-resizer"
        aria-label="拖拽调整侧边栏宽度"
        title="向右拖拽展开，向左拖拽变为窄栏或隐藏"
        @pointerdown="startSidebarResize"
      />
    </aside>

    <WorkspaceTabBar
      :tabs="workspaceState.tabs"
      :active-tab-id="workspaceState.activeTabId"
      :can-restore="workspaceState.recentlyClosed.length > 0"
      @activate="activateTab"
      @close="closeTab"
      @close-others="closeOtherTabs"
      @toggle-pin="toggleTabPin"
      @restore="restoreClosedTab"
      @reorder="reorderTab"
      @back="navigateTabHistory(-1)"
      @forward="navigateTabHistory(1)"
    />

    <section class="system-main">
      <main class="system-content">
        <router-view />
      </main>
    </section>

    <div
      v-if="resizing"
      class="sidebar-resize-guard"
      aria-hidden="true"
      @pointermove="handleSidebarResize"
      @pointerup="stopSidebarResize"
    />

    <GlobalCommandCenter
      v-model:visible="commandCenterVisible"
      @navigate="navigateFromCommandCenter"
      @action="executeWorkspaceAction"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MessagePlugin } from '@/ui/message'
import { useAuthStore } from '@/store/auth'
import { getSidebarNavOrder, setSystemSetting } from '@/api/system'
import WorkspaceTabBar from '@/components/workspace/WorkspaceTabBar.vue'
import GlobalCommandCenter from '@/components/workspace/GlobalCommandCenter.vue'
import {
  activateWorkspaceTab,
  closeOtherWorkspaceTabs,
  closeWorkspaceTab,
  navigateWorkspaceHistory,
  recordWorkspaceRoute,
  reorderWorkspaceTab,
  restoreLastClosedWorkspaceTab,
  restoreWorkspaceState,
  setWorkspaceTabPinned,
  type WorkspaceRouteInput,
} from '@/workspace/workspaceTabs'
import brandLogo from '@/assets/jiqing-wordmark.svg'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
let unsubscribeDesktopWorkspaceCommand: (() => void) | null = null
type SidebarMode = 'full' | 'icon' | 'hidden'
type NavItem = {
  key: string
  path: string
  label: string
  icon: string
  query?: Record<string, string>
  action?: string
  badge?: string
  status?: string
  description?: string
  disabled?: boolean
}
const SIDEBAR_MODE_KEY = 'jiqing-sidebar-mode'
const SIDEBAR_WIDTH_KEY = 'jiqing-sidebar-width'
const SIDEBAR_ORDER_KEY = 'jiqing-sidebar-nav-order'
const WORKSPACE_STORAGE_KEY = 'jiqing-desktop-workspace-v1'
const sidebarMode = ref<SidebarMode>('full')
const sidebarWidth = ref(240)
const resizing = ref(false)
const navOrder = ref<string[]>([])
const draggedModulePath = ref('')
const commandCenterVisible = ref(false)
const workspaceState = ref(restoreWorkspaceState(
  typeof window === 'undefined' ? null : window.sessionStorage.getItem(WORKSPACE_STORAGE_KEY),
))
const userDisplayName = computed(() => authStore.displayName || authStore.username || '用户')
const userInitial = computed(() => userDisplayName.value.trim().slice(0, 1).toUpperCase() || '用')
const userAvatarUrl = computed(() => authStore.user?.avatarUrl || '')

const shellStyle = computed(() => (
  sidebarMode.value === 'full'
    ? { '--sidebar-width': `${sidebarWidth.value}px` }
    : undefined
))

const mainNav: NavItem[] = [
  { key: 'home', path: '/', label: '工作台', icon: 'dashboard', badge: '总览', status: 'live' },
  { key: 'bidding', path: '/bidding', label: '招投标', icon: 'file-paste', badge: '建设中', status: 'pending' },
  { key: 'project', path: '/project-management', label: '项目管理', icon: 'task', badge: '已启用', status: 'enabled' },
  { key: 'audit', path: '/audit', label: '审计', icon: 'view-module', badge: '已启用', status: 'enabled' },
  { key: 'materials', path: '/materials', label: '资料', icon: 'folder', badge: '已启用', status: 'enabled' },
  { key: 'finance', path: '/finance', label: '结算', icon: 'list', badge: '已启用', status: 'enabled' },
]

const defaultNavOrder = mainNav.map((item) => item.path)
const canReorderModules = computed(() => authStore.isAdmin && sidebarMode.value === 'full')
const orderedMainNav = computed(() => {
  const order = normalizeNavOrder(navOrder.value)
  return order.map((path) => mainNav.find((item) => item.path === path)).filter(Boolean) as typeof mainNav
})
const activeModule = computed(() => {
  if (route.path.startsWith('/admin')) return adminModule
  if (route.path.startsWith('/settings')) return personalModule
  return orderedMainNav.value.find((item) => isTopNavActive(item.path)) || orderedMainNav.value[0]
})
const currentSideNav = computed(() => {
  const key = activeModule.value?.path || '/'
  return sideNavMap[key] || sideNavMap['/']
})
const activeSideNavKey = computed(() => {
  const withQuery = currentSideNav.value.find((item) => !item.disabled && item.query && matchesSideNavQuery(item))
  if (withQuery) return withQuery.key
  const actionFallback = currentSideNav.value.find((item) => !item.disabled && item.action && route.path === item.path)
  if (actionFallback && !currentSideNav.value.some((item) => !item.disabled && item.query && route.path === item.path)) return actionFallback.key
  const exact = currentSideNav.value.find((item) => !item.disabled && !item.query && !item.action && route.path === item.path)
  if (exact) return exact.key
  const nested = currentSideNav.value.find((item) => !item.disabled && item.path !== '/' && route.path.startsWith(`${item.path}/`))
  if (nested) return nested.key
  return currentSideNav.value.find((item) => !item.disabled)?.key || currentSideNav.value[0]?.key || ''
})

const adminModule: NavItem = { key: 'admin', path: '/admin/field-configs', label: '后台管理', icon: 'setting', badge: '管理', status: 'enabled' }
const personalModule: NavItem = { key: 'personal-settings', path: '/settings', label: '个人设置', icon: 'user', status: 'enabled' }
const sideNavMap: Record<string, NavItem[]> = {
  '/': [
    { key: 'home-overview', path: '/', label: '数据总览', icon: 'dashboard', description: '查看系统核心指标和待办提醒' },
    { key: 'home-todo', path: '/', label: '我的待办', icon: 'list', badge: '规划中', disabled: true },
    { key: 'home-shortcut', path: '/', label: '快捷入口', icon: 'view-module', badge: '规划中', disabled: true },
  ],
  '/project-management': [
    { key: 'project-ledger', path: '/project-management', query: { view: 'ledger' }, label: '项目台账', icon: 'task', description: '统一查看项目主档案' },
    { key: 'project-create', path: '/project-management', label: '手工创建项目', icon: 'add', action: 'project:create', description: '上传合同并手工复核后创建正式项目' },
    { key: 'project-docs', path: '/project-management', query: { onlyMissingDocuments: '1', sort: 'updatedAt' }, label: '资料缺口', icon: 'folder', description: '筛选仍需补齐资料的项目' },
    { key: 'project-audit', path: '/project-management', query: { view: 'audit' }, label: '审计联动', icon: 'view-module', description: '查看已进入审计流程的项目' },
  ],
  '/materials': [
    { key: 'materials-library', path: '/materials', query: { view: 'library' }, label: '资料库', icon: 'folder', description: '按项目、类型和阶段检索文件' },
    { key: 'materials-pdf', path: '/materials', query: { fileType: 'pdf' }, label: 'PDF 资料', icon: 'file-paste', description: '快速查看可预览的 PDF 资料' },
    { key: 'materials-upload', path: '/materials', label: '上传资料', icon: 'upload', action: 'materials:upload', description: '选择项目和资料类型上传' },
    { key: 'materials-rules', path: '/admin/settings', label: '上传规则', icon: 'list', badge: '管理', description: '配置资料上传限制和系统参数', disabled: !authStore.isAdmin },
  ],
  '/audit': [
    { key: 'audit-board', path: '/audit', query: { mode: 'kanban' }, label: '阶段看板', icon: 'view-module', description: '按审计阶段推进项目' },
    { key: 'audit-table', path: '/audit', query: { mode: 'table' }, label: '审计台账', icon: 'list', description: '查看表格和字段配置后的数据' },
    { key: 'audit-gantt', path: '/audit', query: { mode: 'gantt' }, label: '甘特视图', icon: 'list', description: '按计划时间查看审计排期' },
    { key: 'audit-start', path: '/audit', label: '发起审计', icon: 'add', action: 'audit:start-from-project', description: '从项目主档案进入审计流程' },
    { key: 'audit-attachments', path: '/audit', query: { focus: 'work-items' }, label: '附件与待办', icon: 'file-paste', description: '聚焦审计待办、附件和操作记录' },
  ],
  '/bidding': [
    { key: 'bidding-opportunities', path: '/bidding', query: { view: 'opportunities' }, label: '机会发现', icon: 'dashboard', description: '聚合常用招投标网站采集结果' },
    { key: 'bidding-opening', path: '/bidding', query: { view: 'opening' }, label: '待开标提醒', icon: 'list', description: '围绕真实开标日期形成提醒看板' },
    { key: 'bidding-records', path: '/bidding', query: { view: 'records' }, label: '开标记录', icon: 'file-paste', description: '沉淀开标记录并用于报价分析' },
    { key: 'bidding-price', path: '/bidding', query: { view: 'price' }, label: '报价预测', icon: 'list', description: '基于真实开标记录预测报价区间' },
  ],
  '/finance': [
    { key: 'finance-dashboard', path: '/finance', query: { view: 'overview' }, label: '结算管理概览', icon: 'dashboard', description: '查看结算财务核心指标' },
    { key: 'finance-workbench', path: '/finance', query: { view: 'workbench' }, label: '财务工作台', icon: 'list', description: '处理发票、收付款和风险待办' },
    { key: 'finance-ledger', path: '/finance', query: { view: 'ledger' }, label: '项目结算台账', icon: 'file-paste', description: '按项目查看结算状态和金额' },
    { key: 'finance-invoice', path: '/finance', query: { view: 'invoice' }, label: '发票管理', icon: 'file-paste', description: '管理每个项目的发票开具状态' },
    { key: 'finance-payment', path: '/finance', query: { view: 'payment' }, label: '收付款管理', icon: 'list', description: '登记项目收款、付款和银行回单' },
    { key: 'finance-documents', path: '/finance', query: { view: 'documents' }, label: '结算资料', icon: 'folder', description: '管理付款流程资料和结算留痕' },
    { key: 'finance-retention', path: '/finance', query: { view: 'retention' }, label: '质保金管理', icon: 'folder', description: '跟踪质保金到期和退还状态' },
    { key: 'finance-existing-project', path: '/finance', label: '纳入结算管理', icon: 'add', action: 'finance:add-existing-project', description: '从项目管理选择真实项目并生成结算台账', disabled: !authStore.isEditor },
  ],
  '/admin/field-configs': [
    { key: 'admin-fields', path: '/admin/field-configs', label: '字段配置', icon: 'edit-1', description: '配置审计详情和表单字段' },
    { key: 'admin-options', path: '/admin/field-options', label: '选项配置', icon: 'list', description: '维护业务数据字典' },
    { key: 'admin-theme', path: '/admin/settings', label: '主题设置', icon: 'system-setting', description: '配置品牌、上传限制和系统参数' },
    { key: 'admin-users', path: '/admin/users', label: '用户管理', icon: 'usergroup', description: '维护用户账号、角色和权限' },
    { key: 'admin-logs', path: '/admin/operation-logs', label: '操作记录', icon: 'file-paste', description: '查看系统操作留痕' },
  ],
  '/settings': [
    { key: 'settings-profile', path: '/settings', query: { section: 'profile' }, label: '个人资料', icon: 'user', description: '修改姓名、头像和工作信息' },
    { key: 'settings-sync', path: '/settings', query: { section: 'sync' }, label: '文件同步', icon: 'folder', description: '设置 Windows 本机同步文件夹' },
    { key: 'settings-security', path: '/settings', query: { section: 'security' }, label: '账号安全', icon: 'lock-on', description: '修改当前账号登录密码' },
    { key: 'settings-about', path: '/settings', query: { section: 'about' }, label: '关于与更新', icon: 'info-circle', description: '查看客户端版本并检查更新' },
  ],
}

function normalizeNavOrder(order: string[]) {
  const allowed = new Set(defaultNavOrder)
  const next = order.filter((path, index) => allowed.has(path) && order.indexOf(path) === index)
  return [...next, ...defaultNavOrder.filter((path) => !next.includes(path))]
}

function getModuleTitle(item: typeof mainNav[number]) {
  const statusText = item.badge ? `状态：${item.badge}` : ''
  const dragText = canReorderModules.value ? '可拖拽调整模块顺序' : ''
  return [item.label, statusText, dragText].filter(Boolean).join(' · ')
}

function isTopNavActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

function isSideNavActive(item: NavItem) {
  return item.key === activeSideNavKey.value
}

function sideNavTarget(item: NavItem) {
  return item.query ? { path: item.path, query: item.query } : item.path
}

function matchesSideNavQuery(item: NavItem) {
  if (route.path !== item.path || !item.query) return false
  return Object.entries(item.query).every(([key, value]) => route.query[key] === value)
}

function handleSideNavClick(item: NavItem, event: MouseEvent) {
  if (item.disabled) {
    event.preventDefault()
    MessagePlugin.info(`${item.label}正在规划中`)
    return
  }
  if (item.action) {
    event.preventDefault()
    window.dispatchEvent(new CustomEvent('jiqing-sidebar-action', { detail: { action: item.action, key: item.key } }))
  }
}

function setSidebarMode(mode: SidebarMode) {
  sidebarMode.value = mode
  if (mode === 'full' && sidebarWidth.value < 216) sidebarWidth.value = 240
}

function toggleSidebarMode() {
  setSidebarMode(sidebarMode.value === 'full' ? 'icon' : 'full')
}

onMounted(async () => {
  recordCurrentWorkspaceRoute()
  const saved = window.localStorage.getItem(SIDEBAR_MODE_KEY)
  if (saved === 'full' || saved === 'icon' || saved === 'hidden') {
    sidebarMode.value = saved
  }
  const savedWidth = Number(window.localStorage.getItem(SIDEBAR_WIDTH_KEY) || 0)
  if (savedWidth >= 216 && savedWidth <= 360) sidebarWidth.value = savedWidth
  const savedOrder = safeParseNavOrder(window.localStorage.getItem(SIDEBAR_ORDER_KEY))
  navOrder.value = savedOrder.length ? savedOrder : defaultNavOrder
  window.addEventListener('keydown', handleWorkspaceKeyboard)
  window.addEventListener('mouseup', handleWorkspaceMouseNavigation)
  unsubscribeDesktopWorkspaceCommand = window.jiqingDesktop?.onWorkspaceCommand(
    handleDesktopWorkspaceCommand,
  ) || null
  await loadSidebarNavOrder()
})

watch(sidebarMode, (mode) => {
  window.localStorage.setItem(SIDEBAR_MODE_KEY, mode)
})

watch(sidebarWidth, (width) => {
  window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(width))
})

watch(navOrder, (order) => {
  window.localStorage.setItem(SIDEBAR_ORDER_KEY, JSON.stringify(normalizeNavOrder(order)))
}, { deep: true })

watch(
  () => route.fullPath,
  () => recordCurrentWorkspaceRoute(),
)

watch(workspaceState, (state) => {
  window.sessionStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(state))
}, { deep: true })

watch(() => authStore.isAuthenticated, (authenticated) => {
  if (authenticated) loadSidebarNavOrder()
})

function handleSidebarResize(event: PointerEvent) {
  if (!resizing.value) return
  event.preventDefault()
  const nextWidth = event.clientX
  if (nextWidth < 42) {
    sidebarMode.value = 'hidden'
    stopSidebarResize()
    return
  }
  if (nextWidth < 164) {
    sidebarMode.value = 'icon'
    return
  }
  sidebarMode.value = 'full'
  sidebarWidth.value = Math.max(216, Math.min(360, nextWidth))
}

function stopSidebarResize() {
  resizing.value = false
  document.body.classList.remove('is-resizing-sidebar')
  document.documentElement.classList.remove('is-resizing-sidebar')
  window.getSelection()?.removeAllRanges()
  window.removeEventListener('pointermove', handleSidebarResize)
  window.removeEventListener('pointerup', stopSidebarResize)
  window.removeEventListener('selectstart', preventResizeSelection, true)
  window.removeEventListener('dragstart', preventResizeSelection, true)
}

function startSidebarResize(event: PointerEvent) {
  event.preventDefault()
  event.stopPropagation()
  ;(event.currentTarget as HTMLElement | null)?.setPointerCapture?.(event.pointerId)
  resizing.value = true
  document.body.classList.add('is-resizing-sidebar')
  document.documentElement.classList.add('is-resizing-sidebar')
  window.getSelection()?.removeAllRanges()
  window.addEventListener('pointermove', handleSidebarResize)
  window.addEventListener('pointerup', stopSidebarResize)
  window.addEventListener('selectstart', preventResizeSelection, true)
  window.addEventListener('dragstart', preventResizeSelection, true)
}

onBeforeUnmount(() => {
  stopSidebarResize()
  window.removeEventListener('keydown', handleWorkspaceKeyboard)
  window.removeEventListener('mouseup', handleWorkspaceMouseNavigation)
  unsubscribeDesktopWorkspaceCommand?.()
  unsubscribeDesktopWorkspaceCommand = null
})

function preventResizeSelection(event: Event) {
  if (!resizing.value) return
  event.preventDefault()
}

function safeParseNavOrder(raw: string | null) {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? normalizeNavOrder(parsed) : []
  } catch {
    return []
  }
}

async function loadSidebarNavOrder() {
  if (!authStore.isAuthenticated) return
  try {
    const value = await getSidebarNavOrder()
    if (value?.order?.length) navOrder.value = normalizeNavOrder(value.order)
  } catch {
    // 网络或登录状态异常时保留本地顺序。
  }
}

function startModuleDrag(path: string, event: DragEvent) {
  if (!canReorderModules.value) return
  draggedModulePath.value = path
  event.dataTransfer?.setData('text/plain', path)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function dragOverModule(path: string) {
  if (!draggedModulePath.value || draggedModulePath.value === path) return
  const order = normalizeNavOrder(navOrder.value)
  const from = order.indexOf(draggedModulePath.value)
  const to = order.indexOf(path)
  if (from < 0 || to < 0) return
  order.splice(to, 0, order.splice(from, 1)[0])
  navOrder.value = order
}

async function dropModule(path: string) {
  if (!canReorderModules.value || !draggedModulePath.value) return
  dragOverModule(path)
  await saveSidebarNavOrder()
}

function finishModuleDrag() {
  draggedModulePath.value = ''
}

async function saveSidebarNavOrder() {
  const order = normalizeNavOrder(navOrder.value)
  navOrder.value = order
  try {
    await setSystemSetting('sidebar_nav_order', { order }, authStore.username)
    MessagePlugin.success('侧边栏模块顺序已保存')
  } catch {
    MessagePlugin.warning('模块顺序已保存在当前浏览器，系统设置暂未同步')
  }
}

function currentWorkspaceRoute(): WorkspaceRouteInput {
  return {
    path: route.path,
    fullPath: route.fullPath,
    query: route.query as Record<string, unknown>,
    metaTitle: typeof route.meta.title === 'string' ? route.meta.title : '',
  }
}

function recordCurrentWorkspaceRoute() {
  workspaceState.value = recordWorkspaceRoute(workspaceState.value, currentWorkspaceRoute())
}

async function navigateToWorkspaceRoute(target: string) {
  if (!target || target === route.fullPath) return
  await router.push(target)
}

async function activateTab(tabId: string) {
  const result = activateWorkspaceTab(workspaceState.value, tabId)
  workspaceState.value = result.state
  await navigateToWorkspaceRoute(result.route)
}

async function closeTab(tabId: string) {
  const result = closeWorkspaceTab(workspaceState.value, tabId)
  workspaceState.value = result.state
  if (result.route) await navigateToWorkspaceRoute(result.route)
}

function closeOtherTabs(tabId: string) {
  workspaceState.value = closeOtherWorkspaceTabs(workspaceState.value, tabId)
}

function toggleTabPin(tabId: string) {
  const tab = workspaceState.value.tabs.find((item) => item.id === tabId)
  if (!tab) return
  workspaceState.value = setWorkspaceTabPinned(workspaceState.value, tabId, !tab.pinned)
}

async function restoreClosedTab() {
  const result = restoreLastClosedWorkspaceTab(workspaceState.value)
  workspaceState.value = result.state
  if (result.route) await navigateToWorkspaceRoute(result.route)
}

function reorderTab(tabId: string, targetIndex: number) {
  workspaceState.value = reorderWorkspaceTab(workspaceState.value, tabId, targetIndex)
}

async function navigateTabHistory(direction: -1 | 1) {
  const result = navigateWorkspaceHistory(workspaceState.value, direction)
  workspaceState.value = result.state
  if (result.route) await navigateToWorkspaceRoute(result.route)
}

function handleWorkspaceKeyboard(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  const editing = Boolean(target?.closest('input, textarea, [contenteditable="true"]'))
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    commandCenterVisible.value = true
    return
  }
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 't') {
    event.preventDefault()
    restoreClosedTab()
    return
  }
  if (editing || !event.altKey) return
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    navigateTabHistory(-1)
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    navigateTabHistory(1)
  }
}

function handleWorkspaceMouseNavigation(event: MouseEvent) {
  if (event.button === 3) navigateTabHistory(-1)
  if (event.button === 4) navigateTabHistory(1)
}

function handleDesktopWorkspaceCommand(command: string) {
  if (command === 'workspace:back') navigateTabHistory(-1)
  if (command === 'workspace:forward') navigateTabHistory(1)
  if (command === 'workspace:command-center') commandCenterVisible.value = true
  if (command === 'workspace:restore-closed-tab') restoreClosedTab()
}

async function navigateFromCommandCenter(target: string) {
  await navigateToWorkspaceRoute(target)
}

async function executeWorkspaceAction(action: string) {
  if (action === 'desktop:open-sync-folder') {
    if (!window.jiqingDesktop) {
      MessagePlugin.info('请在 Windows 桌面客户端中打开本地同步目录')
      return
    }
    try {
      await window.jiqingDesktop.openSyncFolder()
    } catch {
      MessagePlugin.warning('尚未设置本地同步目录，请先到资料中心完成设置')
    }
    return
  }

  const targetPath = action === 'materials:upload' ? '/materials' : '/project-management'
  if (route.path !== targetPath) await router.push(targetPath)
  await nextTick()
  window.dispatchEvent(new CustomEvent('jiqing-sidebar-action', { detail: { action } }))
}

async function logout() {
  await authStore.logout()
  MessagePlugin.success('已退出')
  router.push('/login')
}
</script>

<style scoped>
.system-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--sidebar-width, 240px) minmax(0, 1fr);
  grid-template-rows: 58px 40px minmax(0, 1fr);
  grid-template-areas:
    "topbar topbar"
    "sidebar tabs"
    "sidebar main";
  background: var(--bg-page);
  color: var(--text-primary);
}

.system-shell--icon {
  grid-template-columns: 76px minmax(0, 1fr);
}

.system-shell--hidden {
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas:
    "topbar"
    "tabs"
    "main";
}

.platform-topbar {
  grid-area: topbar;
  position: sticky;
  top: 0;
  z-index: 50;
  min-width: 0;
  display: grid;
  grid-template-columns: 228px minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  padding: 0 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(248, 251, 255, 0.76));
  border-bottom: 1px solid rgba(128, 158, 210, 0.14);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.92) inset, 0 12px 32px rgba(36, 67, 120, 0.055);
  backdrop-filter: blur(14px) saturate(128%);
  -webkit-backdrop-filter: blur(14px) saturate(128%);
}

.topbar-brand {
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: center;
  text-decoration: none;
}

.topbar-brand img {
  width: 216px;
  height: auto;
  display: block;
}

.platform-nav {
  min-width: 0;
  width: fit-content;
  max-width: 100%;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px;
  background: rgba(244, 248, 255, 0.68);
  border: 1px solid rgba(129, 157, 205, 0.14);
  border-radius: 999px;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.82) inset;
  overflow-x: auto;
  scrollbar-width: none;
}

.platform-nav::-webkit-scrollbar {
  display: none;
}

.platform-link {
  position: relative;
  height: 34px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 13px;
  color: var(--text-secondary);
  border: 1px solid transparent;
  border-radius: 999px;
  text-decoration: none;
  font-size: 13px;
  line-height: 1;
  transition:
    color var(--duration-fast),
    background var(--duration-fast),
    border-color var(--duration-fast),
    box-shadow var(--duration-fast),
    transform var(--duration-fast);
}

.platform-link:hover,
.platform-link--active {
  color: #0f43d6;
  background: rgba(255, 255, 255, 0.92);
  border-color: rgba(22, 93, 255, 0.12);
  box-shadow: 0 6px 18px rgba(42, 88, 170, 0.08);
}

.platform-link--active {
  font-weight: 700;
}

.platform-link--active::after {
  content: '';
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 3px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, #165dff, #14c9c9);
  opacity: .78;
}

.platform-link--draggable {
  cursor: grab;
}

.platform-link--dragging {
  opacity: .5;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topbar-command-trigger {
  height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 8px 0 11px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(128, 158, 210, 0.16);
  border-radius: 999px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.topbar-command-trigger:hover {
  color: #0f43d6;
  background: rgba(255, 255, 255, 0.88);
  border-color: rgba(22, 93, 255, 0.18);
}

.topbar-command-trigger kbd {
  min-width: 40px;
  height: 20px;
  display: inline-grid;
  place-items: center;
  padding: 0 6px;
  color: var(--text-tertiary);
  background: rgba(242, 246, 252, 0.9);
  border: 1px solid rgba(128, 158, 210, 0.18);
  border-radius: 5px;
  font: inherit;
  font-size: 10px;
}

.topbar-user {
  position: relative;
  height: 42px;
  max-width: 240px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px 0 18px;
  color: #12213b;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(22, 93, 255, 0.14), rgba(20, 201, 201, 0.08)),
    rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(22, 93, 255, 0.16);
  border-radius: 999px;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, .78) inset,
    0 10px 26px rgba(55, 92, 155, 0.1);
  text-decoration: none;
}

.topbar-user::before {
  content: '';
  width: 6px;
  height: 6px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #165dff;
  box-shadow: 0 0 0 5px rgba(22, 93, 255, 0.1);
}

.topbar-user span {
  color: #5f6f8f;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.topbar-user__avatar {
  width: 30px;
  height: 30px;
  overflow: hidden;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  color: #fff !important;
  border-radius: 50%;
  background: linear-gradient(145deg, #165dff, #0f43d6);
}

.topbar-user__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.topbar-user__avatar > span {
  color: inherit;
  font-size: 12px;
  font-weight: 800;
}

.topbar-user__copy {
  min-width: 0;
  display: grid;
}

.topbar-user__copy small {
  color: #8490a6;
  font-size: 10px;
  line-height: 1.1;
}

.topbar-user strong {
  max-width: 126px;
  overflow: hidden;
  color: #0f43d6;
  font-size: 14px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-action-link,
.topbar-icon-button {
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 11px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.56);
  border: 1px solid rgba(128, 158, 210, 0.16);
  border-radius: 999px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-decoration: none;
  box-shadow: 0 1px 0 rgba(255, 255, 255, .72) inset;
}

.topbar-icon-button {
  width: 34px;
  padding: 0;
}

.topbar-action-link:hover,
.topbar-icon-button:hover {
  color: #0f43d6;
  border-color: rgba(22, 93, 255, 0.18);
  background: #fff;
}

.topbar-action-link--primary {
  color: var(--text-on-brand);
  background: var(--color-brand-500);
  border-color: var(--color-brand-500);
}

.system-sidebar {
  grid-area: sidebar;
  position: relative;
  min-height: calc(100vh - 58px);
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 12px 10px 14px;
  background: linear-gradient(180deg, rgba(235, 244, 255, 0.94) 0%, rgba(248, 251, 255, 0.98) 52%, #fff 100%);
  border-right: 0;
  color: var(--text-primary);
  min-width: 0;
}

.sidebar-restore {
  position: fixed;
  top: var(--space-4);
  left: var(--space-4);
  z-index: 100;
  min-height: 36px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3);
  color: var(--color-brand-500);
  background: var(--bg-surface);
  border: 1px solid var(--color-brand-200);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  font: inherit;
}

.system-shell--icon .system-sidebar {
  gap: var(--space-3);
  padding: var(--space-3) var(--space-2);
}

.module-nav,
.nav-group {
  display: grid;
  gap: 6px;
}

.module-nav {
  align-self: start;
  min-height: 0;
  overflow: auto;
  padding: 0;
}

.sidebar-module-heading {
  min-height: 44px;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  color: var(--color-brand-500);
}

.sidebar-module-heading__icon {
  width: 24px;
  height: 24px;
  display: inline-grid;
  place-items: center;
}

.sidebar-module-heading strong {
  overflow: hidden;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-module-caret {
  width: 8px;
  height: 8px;
  justify-self: center;
  border-top: 1.5px solid currentColor;
  border-left: 1.5px solid currentColor;
  transform: translateY(2px) rotate(45deg);
}

.sidebar-module-items {
  display: grid;
  gap: 4px;
}

.nav-section-title {
  margin: 0 0 2px;
  padding: 0 10px;
  color: #8492a8;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
}

.nav-group {
  align-self: start;
  min-height: 0;
  padding-top: 12px;
  border-top: 1px solid rgba(128, 158, 210, 0.14);
}

.nav-group p {
  margin: 0 0 var(--space-1);
  padding: 0 10px;
  color: #8492a8;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
}

.module-link {
  position: relative;
  width: 100%;
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px 0 34px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-align: left;
  text-decoration: none;
  transition: background var(--duration-fast), border-color var(--duration-fast), color var(--duration-fast), box-shadow var(--duration-fast);
}

.module-link:hover,
.module-link--active {
  background: rgba(255, 255, 255, 0.68);
  border-color: transparent;
  color: #0f43d6;
}

.module-link--active {
  background: #fff;
  font-weight: 700;
  box-shadow: none;
}

.module-link--active::before {
  content: none;
}

.module-link :deep(.arco-icon) { flex: 0 0 auto; }
.module-link span { flex: 1; min-width: 0; }
.module-link__icon {
  width: 24px;
  height: 24px;
  flex: 0 0 24px !important;
  display: inline-grid;
  place-items: center;
  color: #8b96a8;
  background: transparent;
  border-radius: 8px;
}

.module-link--active .module-link__icon,
.module-link:hover .module-link__icon {
  color: #165dff;
  background: transparent;
}

.module-link small {
  flex: 0 0 auto;
  padding: 1px 6px;
  color: #7b8aa2;
  background: rgba(239, 245, 255, .86);
  border-radius: 999px;
  font-size: 10px;
  line-height: 1.5;
}

.module-link--disabled {
  opacity: .62;
}

.route-sense {
  display: grid;
  gap: 6px;
  padding: 11px 12px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, .5);
  border: 1px solid rgba(128, 158, 210, 0.16);
  border-radius: 10px;
}

.route-sense strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.route-sense span {
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}

.sidebar-context-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid rgba(128, 158, 210, 0.16);
  border-radius: 10px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, .74), rgba(239, 247, 255, .46));
  box-shadow: 0 10px 24px rgba(61, 105, 185, 0.06);
}

.sidebar-context-card p,
.sidebar-context-card strong,
.sidebar-context-card span {
  margin: 0;
}

.sidebar-context-card p {
  color: #8492a8;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
}

.sidebar-context-card strong {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.3;
}

.sidebar-context-card span {
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.55;
}

.module-status-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  display: block;
  margin-left: auto;
  border-radius: 999px;
  background: var(--text-tertiary);
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 12%, transparent);
}

.module-status-dot--live {
  background: var(--color-brand-500);
}

.module-status-dot--enabled {
  background: var(--color-success);
}

.module-status-dot--pending {
  background: var(--color-warning);
}

.module-link--active .module-status-dot {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-brand-500) 16%, transparent);
}

.module-link--draggable {
  cursor: grab;
}

.module-link--draggable:active {
  cursor: grabbing;
}

.module-link--dragging {
  opacity: .48;
  border-color: var(--color-brand-300);
  background: var(--color-brand-50);
}

.module-link--disabled {
  opacity: .78;
}

.sidebar-foot {
  display: flex;
  justify-content: flex-end;
  align-self: end;
  min-width: 0;
  padding: 8px 2px 0;
  border-top: 0;
}

.sidebar-collapse-toggle {
  min-width: 62px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(128, 158, 210, 0.12);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(31, 64, 108, 0.04);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.sidebar-collapse-toggle:hover {
  color: var(--color-brand-500);
  background: #fff;
}

.system-shell--icon .sidebar-module-heading {
  grid-template-columns: 1fr;
  justify-items: center;
  padding: 0;
}

.system-shell--icon .sidebar-module-heading strong,
.system-shell--icon .sidebar-module-caret,
.system-shell--icon .sidebar-collapse-toggle span {
  display: none;
}

.system-shell--icon .module-link {
  justify-content: center;
  padding-inline: 0;
}

.system-shell--icon .sidebar-foot {
  justify-content: center;
}

.system-shell--icon .sidebar-collapse-toggle {
  width: 40px;
  min-width: 40px;
  padding: 0;
}

.sidebar-resizer {
  position: absolute;
  top: 0;
  right: -4px;
  bottom: 0;
  z-index: 5;
  width: 8px;
  padding: 0;
  background: transparent;
  border: 0;
  cursor: col-resize;
}

.sidebar-resizer::after {
  content: '';
  position: absolute;
  top: 0;
  right: 3px;
  width: 2px;
  height: 100%;
  background: color-mix(in srgb, var(--border-color) 72%, transparent);
  transition: width var(--duration-fast), background var(--duration-fast);
}

.sidebar-resizer:hover::after,
.system-shell--resizing .sidebar-resizer::after {
  width: 3px;
  background: var(--color-brand-400);
}

:global(body.is-resizing-sidebar) {
  cursor: col-resize;
  user-select: none;
}

.sidebar-resize-guard {
  position: fixed;
  inset: 0;
  z-index: 999;
  cursor: col-resize;
  background: transparent;
  user-select: none;
}

:global(html.is-resizing-sidebar),
:global(html.is-resizing-sidebar *),
:global(body.is-resizing-sidebar),
:global(body.is-resizing-sidebar *) {
  cursor: col-resize !important;
  user-select: none !important;
  -webkit-user-select: none !important;
}

.system-main {
  grid-area: main;
  min-width: 0;
  min-height: calc(100vh - 98px);
  display: grid;
  grid-template-rows: minmax(0, 1fr);
}

.system-content {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: var(--space-5) var(--space-6) var(--space-6);
  background: transparent;
}

@media (max-width: 900px) {
  .system-shell {
    grid-template-columns: 72px minmax(0, 1fr);
    grid-template-rows: auto 40px minmax(0, 1fr);
  }
  .system-shell--hidden {
    grid-template-columns: minmax(0, 1fr);
  }
  .platform-topbar {
    grid-template-columns: 176px minmax(0, 1fr) auto;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
  }
  .topbar-brand img { width: 152px; }
  .platform-link { padding: 0 9px; }
  .platform-link em { display: none; }
  .topbar-user {
    height: 34px;
    max-width: 132px;
    gap: 6px;
    padding: 0 10px;
  }
  .topbar-user::before { display: none; }
  .topbar-user__copy { display: none; }
  .topbar-user strong { max-width: 96px; font-size: 12px; }
  .topbar-action-link span { display: none; }
  .topbar-action-link { width: 34px; padding: 0; }
  .topbar-command-trigger span,
  .topbar-command-trigger kbd { display: none; }
  .topbar-command-trigger { width: 34px; padding: 0; justify-content: center; }
  .system-sidebar { padding: var(--space-3) var(--space-2); gap: var(--space-3); }
  .sidebar-module-heading strong,
  .sidebar-module-caret,
  .module-link span,
  .module-link small,
  .nav-group p,
  .route-sense,
  .sidebar-context-card,
  .sidebar-collapse-toggle span { display: none; }
  .sidebar-module-heading { grid-template-columns: 1fr; justify-items: center; padding: 0; }
  .module-link { justify-content: center; padding: 0; min-height: 42px; }
  .sidebar-foot { justify-content: center; }
  .sidebar-collapse-toggle { width: 40px; min-width: 40px; padding: 0; }
  .system-content { padding: var(--space-3); }
}

@media (max-width: 640px) {
  .system-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto 40px minmax(0, 1fr);
    grid-template-areas:
      "topbar"
      "sidebar"
      "tabs"
      "main";
  }
  .system-shell--hidden {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto 40px minmax(0, 1fr);
    grid-template-areas:
      "topbar"
      "tabs"
      "main";
  }
  .platform-topbar {
    position: sticky;
    grid-template-columns: 1fr auto;
    grid-template-areas:
      "brand actions"
      "nav nav";
  }
  .topbar-brand { grid-area: brand; }
  .platform-nav { grid-area: nav; padding-top: 2px; }
  .topbar-actions { grid-area: actions; }
  .topbar-user { display: none; }
  .system-sidebar {
    position: sticky;
    top: 58px;
    z-index: 20;
    min-height: auto;
    grid-template-columns: 1fr;
    grid-template-rows: auto auto;
    gap: var(--space-3);
    padding: var(--space-3);
  }
  .module-nav {
    grid-column: 1 / -1;
    display: flex;
    overflow-x: auto;
    gap: var(--space-2);
    padding-bottom: 2px;
    scrollbar-width: none;
  }
  .sidebar-module-heading { display: none; }
  .sidebar-module-items { display: flex; gap: var(--space-2); }
  .module-nav::-webkit-scrollbar { display: none; }
  .module-link {
    flex: 0 0 auto;
    min-width: 118px;
    justify-content: flex-start;
    padding: 0 var(--space-3);
  }
  .module-link span {
    display: inline;
  }

  .module-status-dot {
    margin-left: auto;
  }
  .nav-group,
  .sidebar-context-card,
  .sidebar-foot { display: none; }
  .system-main { min-height: auto; }
}
</style>
