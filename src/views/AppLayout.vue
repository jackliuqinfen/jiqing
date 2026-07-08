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
          :draggable="canReorderModules"
          :title="getModuleTitle(item)"
          @dragstart="startModuleDrag(item.path, $event)"
          @dragover.prevent="dragOverModule(item.path)"
          @drop.prevent="dropModule(item.path)"
          @dragend="finishModuleDrag"
        >
          <AIcon :name="item.icon" />
          <span>{{ item.label }}</span>
          <em v-if="item.badge">{{ item.badge }}</em>
        </router-link>
      </nav>
      <div class="topbar-actions">
        <button v-if="sidebarMode === 'hidden'" type="button" class="topbar-icon-button" title="展开左侧导航" @click="setSidebarMode('full')">
          <AIcon name="list" />
        </button>
        <router-link v-if="authStore.isAdmin" to="/admin/field-configs" class="topbar-action-link">
          <AIcon name="setting" />
          <span>设置</span>
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
      <div class="system-brand" aria-label="当前模块">
        <span class="brand-copy">
          <strong>{{ activeModule?.label || '工作台' }}</strong>
          <em>{{ activeModuleDescription }}</em>
        </span>
      </div>

      <nav class="module-nav" aria-label="当前模块业务功能">
        <router-link
          v-for="item in currentSideNav"
          :key="item.key"
          :to="item.path"
          class="module-link"
          :class="{ 'module-link--active': isSideNavActive(item), 'module-link--disabled': item.disabled }"
          :title="item.description || item.label"
          @click="handleSideNavClick(item, $event)"
        >
          <AIcon :name="item.icon" />
          <span>{{ item.label }}</span>
          <small v-if="item.badge">{{ item.badge }}</small>
        </router-link>
      </nav>

      <div class="nav-group">
        <p>当前位置</p>
        <div class="route-sense">
          <strong>{{ activeModule?.label || '首页数据看板' }}</strong>
          <span>{{ activeSideNav?.label || '总览' }}</span>
        </div>
      </div>

      <div class="sidebar-foot">
        <div class="sidebar-collapse-actions" aria-label="侧边栏显示方式">
          <button type="button" :class="{ active: sidebarMode === 'full' }" title="展开侧边栏" @click="setSidebarMode('full')">
            <AIcon name="list" />
            <span>展开</span>
          </button>
          <button type="button" :class="{ active: sidebarMode === 'icon' }" title="折叠为图标栏" @click="setSidebarMode('icon')">
            <AIcon name="view-module" />
            <span>窄栏</span>
          </button>
          <button type="button" title="完全收起侧边栏" @click="setSidebarMode('hidden')">
            <AIcon name="eye-invisible" />
            <span>隐藏</span>
          </button>
        </div>
        <div class="sidebar-actions">
          <button type="button" class="sidebar-action" @click="router.push(activeModule?.path || '/')">
            <AIcon name="dashboard" />
            <span>模块首页</span>
          </button>
        </div>
        <div class="system-status">
          <span />
          <strong>系统可用</strong>
          <em>数据已同步</em>
        </div>
      </div>
      <button
        type="button"
        class="sidebar-resizer"
        aria-label="拖拽调整侧边栏宽度"
        title="向右拖拽展开，向左拖拽变为窄栏或隐藏"
        @pointerdown="startSidebarResize"
      />
    </aside>

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
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MessagePlugin } from '@/ui/message'
import { useAuthStore } from '@/store/auth'
import { getSidebarNavOrder, setSystemSetting } from '@/api/system'
import brandLogo from '@/assets/jiqing-wordmark.svg'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
type SidebarMode = 'full' | 'icon' | 'hidden'
type NavItem = {
  key: string
  path: string
  label: string
  icon: string
  badge?: string
  status?: string
  description?: string
  disabled?: boolean
}
const SIDEBAR_MODE_KEY = 'jiqing-sidebar-mode'
const SIDEBAR_WIDTH_KEY = 'jiqing-sidebar-width'
const SIDEBAR_ORDER_KEY = 'jiqing-sidebar-nav-order'
const sidebarMode = ref<SidebarMode>('full')
const sidebarWidth = ref(240)
const resizing = ref(false)
const navOrder = ref<string[]>([])
const draggedModulePath = ref('')

const shellStyle = computed(() => (
  sidebarMode.value === 'full'
    ? { '--sidebar-width': `${sidebarWidth.value}px` }
    : undefined
))

const mainNav: NavItem[] = [
  { key: 'home', path: '/', label: '工作台', icon: 'dashboard', badge: '总览', status: 'live' },
  { key: 'project', path: '/project-management', label: '项目管理', icon: 'task', badge: '已启用', status: 'enabled' },
  { key: 'materials', path: '/materials', label: '资料中心', icon: 'folder', badge: '已启用', status: 'enabled' },
  { key: 'audit', path: '/audit', label: '审计看板', icon: 'view-module', badge: '已启用', status: 'enabled' },
  { key: 'bidding', path: '/bidding', label: '招投标看板', icon: 'file-paste', badge: '建设中', status: 'pending' },
  { key: 'finance', path: '/finance', label: '财务看板', icon: 'list', badge: '建设中', status: 'pending' },
]

const defaultNavOrder = mainNav.map((item) => item.path)
const canReorderModules = computed(() => authStore.isAdmin && sidebarMode.value === 'full')
const orderedMainNav = computed(() => {
  const order = normalizeNavOrder(navOrder.value)
  return order.map((path) => mainNav.find((item) => item.path === path)).filter(Boolean) as typeof mainNav
})
const activeModule = computed(() => {
  if (route.path.startsWith('/admin')) return adminModule
  return orderedMainNav.value.find((item) => isTopNavActive(item.path)) || orderedMainNav.value[0]
})
const activeModuleDescription = computed(() => {
  const key = activeModule.value?.path || '/'
  return moduleDescriptions[key] || '按当前模块聚合业务功能'
})
const currentSideNav = computed(() => {
  const key = activeModule.value?.path || '/'
  return sideNavMap[key] || sideNavMap['/']
})
const activeSideNav = computed(() => currentSideNav.value.find((item) => isSideNavActive(item)))
const activeSideNavKey = computed(() => {
  const exact = currentSideNav.value.find((item) => !item.disabled && route.path === item.path)
  if (exact) return exact.key
  const nested = currentSideNav.value.find((item) => !item.disabled && item.path !== '/' && route.path.startsWith(`${item.path}/`))
  if (nested) return nested.key
  return currentSideNav.value.find((item) => !item.disabled)?.key || currentSideNav.value[0]?.key || ''
})

const adminModule: NavItem = { key: 'admin', path: '/admin/field-configs', label: '后台设置', icon: 'setting', badge: '管理', status: 'enabled' }
const moduleDescriptions: Record<string, string> = {
  '/': '经营数据、待办与跨模块总览',
  '/project-management': '项目主数据、流程与台账',
  '/materials': '项目资料、证据与归档',
  '/audit': '审计流程、阶段与附件',
  '/bidding': '机会、开标与报价分析',
  '/finance': '收款、发票与付款资料',
  '/admin/field-configs': '字段、选项、用户与系统规则',
}
const sideNavMap: Record<string, NavItem[]> = {
  '/': [
    { key: 'home-overview', path: '/', label: '数据总览', icon: 'dashboard', description: '查看系统核心指标和待办提醒' },
    { key: 'home-todo', path: '/', label: '我的待办', icon: 'list', badge: '规划中', disabled: true },
    { key: 'home-shortcut', path: '/', label: '快捷入口', icon: 'view-module', badge: '规划中', disabled: true },
  ],
  '/project-management': [
    { key: 'project-ledger', path: '/project-management', label: '项目台账', icon: 'task', description: '统一查看项目主档案' },
    { key: 'project-create', path: '/project-management', label: '新建向导', icon: 'add', description: '问卷式创建项目' },
    { key: 'project-docs', path: '/project-management', label: '资料节点', icon: 'folder', description: '查看项目资料目录和缺口' },
    { key: 'project-audit', path: '/project-management', label: '审计联动', icon: 'view-module', description: '从项目主档案发起审计' },
  ],
  '/materials': [
    { key: 'materials-library', path: '/materials', label: '资料库', icon: 'folder', description: '按项目、类型和阶段检索文件' },
    { key: 'materials-upload', path: '/materials', label: '上传资料', icon: 'upload', description: '选择项目和资料类型上传' },
    { key: 'materials-rules', path: '/materials', label: '目录规则', icon: 'list', badge: '管理', disabled: !authStore.isAdmin },
  ],
  '/audit': [
    { key: 'audit-board', path: '/audit', label: '阶段看板', icon: 'view-module', description: '按审计阶段推进项目' },
    { key: 'audit-table', path: '/audit', label: '审计台账', icon: 'list', description: '查看表格和字段配置后的数据' },
    { key: 'audit-start', path: '/audit', label: '发起审计', icon: 'add', description: '从项目主档案进入审计流程' },
    { key: 'audit-attachments', path: '/audit', label: '附件与记录', icon: 'file-paste', description: '查看审计附件和操作记录' },
  ],
  '/bidding': [
    { key: 'bidding-opportunities', path: '/bidding', label: '机会发现', icon: 'dashboard', description: '聚合常用招投标网站采集结果' },
    { key: 'bidding-opening', path: '/bidding', label: '待开标提醒', icon: 'list', badge: '规划中', disabled: true },
    { key: 'bidding-records', path: '/bidding', label: '开标记录', icon: 'file-paste', badge: '规划中', disabled: true },
    { key: 'bidding-price', path: '/bidding', label: '报价预测', icon: 'line-chart', badge: '规划中', disabled: true },
  ],
  '/finance': [
    { key: 'finance-project', path: '/finance', label: '项目收款', icon: 'list', description: '按合同阶段管理应收和实收' },
    { key: 'finance-invoice', path: '/finance', label: '发票管理', icon: 'file-paste', badge: '规划中', disabled: true },
    { key: 'finance-payment-docs', path: '/finance', label: '付款资料', icon: 'folder', badge: '规划中', disabled: true },
  ],
  '/admin/field-configs': [
    { key: 'admin-fields', path: '/admin/field-configs', label: '字段配置', icon: 'edit-1', description: '配置审计详情和表单字段' },
    { key: 'admin-options', path: '/admin/field-options', label: '选项配置', icon: 'list', description: '维护业务数据字典' },
    { key: 'admin-theme', path: '/admin/settings', label: '主题设置', icon: 'system-setting', description: '配置品牌、上传限制和系统参数' },
    { key: 'admin-users', path: '/admin/users', label: '用户管理', icon: 'usergroup', description: '维护用户账号、角色和权限' },
    { key: 'admin-logs', path: '/admin/operation-logs', label: '操作记录', icon: 'file-paste', description: '查看系统操作留痕' },
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

function handleSideNavClick(item: NavItem, event: MouseEvent) {
  if (!item.disabled) return
  event.preventDefault()
  MessagePlugin.info(`${item.label}正在规划中`)
}

function setSidebarMode(mode: SidebarMode) {
  sidebarMode.value = mode
  if (mode === 'full' && sidebarWidth.value < 216) sidebarWidth.value = 240
}

onMounted(async () => {
  const saved = window.localStorage.getItem(SIDEBAR_MODE_KEY)
  if (saved === 'full' || saved === 'icon' || saved === 'hidden') {
    sidebarMode.value = saved
  }
  const savedWidth = Number(window.localStorage.getItem(SIDEBAR_WIDTH_KEY) || 0)
  if (savedWidth >= 216 && savedWidth <= 360) sidebarWidth.value = savedWidth
  const savedOrder = safeParseNavOrder(window.localStorage.getItem(SIDEBAR_ORDER_KEY))
  navOrder.value = savedOrder.length ? savedOrder : defaultNavOrder
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

onBeforeUnmount(stopSidebarResize)

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
  grid-template-rows: 58px minmax(0, 1fr);
  grid-template-areas:
    "topbar topbar"
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
    "main";
}

.platform-topbar {
  grid-area: topbar;
  position: sticky;
  top: 0;
  z-index: 50;
  min-width: 0;
  display: grid;
  grid-template-columns: 196px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-5);
  background: rgba(255, 255, 255, 0.76);
  border-bottom: 1px solid rgba(128, 158, 210, 0.18);
  box-shadow: 0 10px 30px rgba(55, 92, 155, 0.06);
  backdrop-filter: blur(18px) saturate(145%);
  -webkit-backdrop-filter: blur(18px) saturate(145%);
}

.topbar-brand {
  min-width: 0;
  display: flex;
  align-items: center;
  text-decoration: none;
}

.topbar-brand img {
  width: 154px;
  height: auto;
  display: block;
}

.platform-nav {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
}

.platform-nav::-webkit-scrollbar {
  display: none;
}

.platform-link {
  height: 38px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 12px;
  color: var(--text-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  text-decoration: none;
  transition: color var(--duration-fast), background var(--duration-fast), border-color var(--duration-fast), box-shadow var(--duration-fast);
}

.platform-link:hover,
.platform-link--active {
  color: var(--color-brand-600);
  background: rgba(255, 255, 255, 0.84);
  border-color: rgba(22, 93, 255, 0.16);
  box-shadow: 0 8px 18px rgba(61, 105, 185, 0.07);
}

.platform-link--active {
  font-weight: 700;
}

.platform-link em {
  padding: 1px 6px;
  color: var(--text-tertiary);
  background: rgba(240, 245, 255, 0.82);
  border-radius: 999px;
  font-size: 10px;
  font-style: normal;
  line-height: 1.5;
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
  gap: var(--space-2);
}

.topbar-action-link,
.topbar-icon-button {
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 12px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(128, 158, 210, 0.22);
  border-radius: var(--radius-md);
  cursor: pointer;
  font: inherit;
  text-decoration: none;
}

.topbar-icon-button {
  width: 34px;
  padding: 0;
}

.topbar-action-link:hover,
.topbar-icon-button:hover {
  color: var(--color-brand-600);
  border-color: var(--color-brand-200);
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
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-3);
  background: var(--bg-surface);
  border-right: 1px solid var(--border-color);
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

.system-brand {
  display: grid;
  align-content: start;
  gap: var(--space-2);
  min-height: auto;
  padding: 0 var(--space-2) var(--space-4);
  color: var(--text-primary);
  text-decoration: none;
  border-bottom: 1px solid var(--border-color);
}

.brand-icon {
  width: 204px;
  height: 124px;
  display: grid;
  align-items: center;
  justify-items: start;
  padding: 0;
  background: transparent;
  border: 0;
  box-shadow: none;
  overflow: visible;
}

.brand-icon img {
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
}

:global(html[data-sidebar-logo='white'] .system-sidebar .brand-icon img) {
  filter: brightness(0) invert(1);
}

:global(html[data-sidebar-logo='white'] .system-sidebar .brand-icon) {
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--color-brand-600), var(--color-brand-500));
}

:global(html[data-sidebar-logo='black'] .system-sidebar .brand-icon img) {
  filter: brightness(0) saturate(100%);
}

.system-brand strong,
.system-brand em {
  display: block;
  font-style: normal;
  line-height: 1.25;
}

.brand-copy { display: grid; gap: 5px; padding-left: 1px; }
.system-brand strong { font-size: var(--text-lg); font-weight: 800; }
.system-brand em { color: var(--text-tertiary); font-size: 11px; }

.system-shell--icon .system-sidebar {
  gap: var(--space-3);
  padding: var(--space-3) var(--space-2);
}

.system-shell--icon .system-brand {
  min-height: 42px;
  justify-items: center;
  padding: var(--space-2) 0 var(--space-3);
}

.system-shell--icon .brand-icon {
  width: 52px;
  height: 40px;
  justify-items: center;
}

.system-shell--icon .brand-copy,
.system-shell--icon .module-link span,
.system-shell--icon .module-link small,
.system-shell--icon .nav-group p,
.system-shell--icon .route-sense,
.system-shell--icon .sidebar-action span,
.system-shell--icon .sidebar-collapse-actions span,
.system-shell--icon .system-status strong,
.system-shell--icon .system-status em {
  display: none;
}

.system-shell--icon .module-link,
.system-shell--icon .sidebar-action,
.system-shell--icon .sidebar-collapse-actions button {
  justify-content: center;
  padding-inline: 0;
}

.system-shell--icon .system-status {
  grid-template-columns: 1fr;
  justify-items: center;
  padding: var(--space-2);
}

.system-shell--icon .sidebar-foot {
  gap: 6px;
}

.system-shell--icon .sidebar-collapse-actions {
  grid-template-columns: 1fr;
}

.system-shell--icon .sidebar-collapse-actions button,
.system-shell--icon .sidebar-action {
  width: 100%;
  height: 34px;
}

.system-shell--icon .system-status span {
  grid-row: auto;
}

.module-nav,
.nav-group {
  display: grid;
  gap: var(--space-1);
}

.nav-group {
  align-self: start;
  min-height: 0;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-color);
}

.nav-group p {
  margin: 0 0 var(--space-1);
  padding: 0 var(--space-3);
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}

.module-link {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  text-align: left;
  text-decoration: none;
}

.module-link:hover,
.module-link--active {
  background: var(--bg-hover);
  border-color: var(--color-brand-100);
  color: var(--color-brand-500);
}

.module-link--active {
  background: var(--bg-active);
  font-weight: 600;
}

.module-link :deep(.arco-icon) { flex: 0 0 auto; }
.module-link span { flex: 1; min-width: 0; }
.module-link small {
  flex: 0 0 auto;
  padding: 1px 6px;
  color: var(--text-tertiary);
  background: var(--bg-muted);
  border-radius: 999px;
  font-size: 10px;
  line-height: 1.5;
}

.module-link--disabled {
  opacity: .62;
}

.route-sense {
  display: grid;
  gap: 5px;
  padding: 10px var(--space-3);
  color: var(--text-secondary);
  background: rgba(255, 255, 255, .48);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.route-sense strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.route-sense span {
  color: var(--text-tertiary);
  font-size: var(--text-xs);
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
  display: grid;
  gap: var(--space-2);
  align-self: end;
  min-width: 0;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-color);
}

.sidebar-actions {
  display: grid;
  gap: 6px;
}

.sidebar-collapse-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  min-width: 0;
}

.sidebar-collapse-actions button {
  min-width: 0;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0 6px;
  color: var(--text-tertiary);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font: inherit;
  font-size: 11px;
}

.sidebar-collapse-actions button:hover,
.sidebar-collapse-actions button.active {
  color: var(--color-brand-500);
  border-color: var(--color-brand-200);
  background: var(--bg-hover);
}

.sidebar-action {
  height: 34px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3);
  color: var(--text-secondary);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  font: inherit;
  text-decoration: none;
}

.sidebar-action:hover {
  color: var(--color-brand-500);
  border-color: var(--color-brand-200);
  background: var(--bg-hover);
}

.system-status {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 8px;
  align-items: center;
  padding: 10px var(--space-3);
  color: var(--text-secondary);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.system-status span {
  width: 8px;
  height: 8px;
  grid-row: span 2;
  background: var(--color-success);
  border-radius: 2px;
}

.system-status strong { font-size: var(--text-xs); font-weight: 600; }
.system-status em { font-size: 10px; font-style: normal; color: var(--text-tertiary); }

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
  min-height: calc(100vh - 58px);
  display: grid;
  grid-template-rows: minmax(0, 1fr);
}

.system-content {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: var(--space-5) var(--space-6) var(--space-6);
  background: #F7F8FA;
}

@media (max-width: 900px) {
  .system-shell {
    grid-template-columns: 72px minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
  }
  .system-shell--hidden {
    grid-template-columns: minmax(0, 1fr);
  }
  .platform-topbar {
    grid-template-columns: 148px minmax(0, 1fr) auto;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
  }
  .topbar-brand img { width: 126px; }
  .platform-link { padding: 0 9px; }
  .platform-link em { display: none; }
  .topbar-action-link span { display: none; }
  .topbar-action-link { width: 34px; padding: 0; }
  .system-sidebar { padding: var(--space-3) var(--space-2); gap: var(--space-3); }
  .system-brand .brand-copy,
  .module-link span,
  .module-link small,
  .nav-group p,
  .route-sense,
  .sidebar-action span,
  .system-status strong,
  .system-status em { display: none; }
  .brand-icon {
    width: 52px;
    height: 39px;
    justify-items: center;
  }
  .module-link { justify-content: center; padding: 0; min-height: 42px; }
  .system-content { padding: var(--space-3); }
}

@media (max-width: 640px) {
  .system-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto minmax(0, 1fr);
    grid-template-areas:
      "topbar"
      "sidebar"
      "main";
  }
  .system-shell--hidden { grid-template-columns: minmax(0, 1fr); }
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
  .system-brand { display: none; }
  .system-brand strong { font-size: var(--text-md); }
  .system-brand em { font-size: 11px; }
  .module-nav {
    grid-column: 1 / -1;
    display: flex;
    overflow-x: auto;
    gap: var(--space-2);
    padding-bottom: 2px;
    scrollbar-width: none;
  }
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
  .sidebar-foot { display: none; }
  .system-main { min-height: auto; }
}
</style>

