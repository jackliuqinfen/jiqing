<template>
  <div class="system-shell" :class="`system-shell--${sidebarMode}`">
    <button v-if="sidebarMode === 'hidden'" type="button" class="sidebar-restore" @click="setSidebarMode('full')">
      <AIcon name="list" />
      <span>展开导航</span>
    </button>

    <aside v-if="sidebarMode !== 'hidden'" class="system-sidebar">
      <router-link to="/" class="system-brand" aria-label="江苏集庆·工程管理系统">
        <span class="brand-icon"><img :src="brandLogo" alt="" /></span>
        <span class="brand-copy">
          <strong>工程管理系统</strong>
          <em>项目协同与审计看板</em>
        </span>
      </router-link>

      <nav class="module-nav" aria-label="业务模块">
        <router-link
          v-for="item in mainNav"
          :key="item.path"
          :to="item.path"
          class="module-link"
          :active-class="item.path === '/' ? '' : 'module-link--active'"
          exact-active-class="module-link--active"
        >
          <AIcon :name="item.icon" />
          <span>{{ item.label }}</span>
          <small v-if="item.badge">{{ item.badge }}</small>
        </router-link>
      </nav>

      <div v-if="authStore.isAdmin" class="nav-group">
        <p>后台管理</p>
        <router-link to="/admin/field-configs" class="module-link">
          <AIcon name="edit-1" />
          <span>字段配置</span>
        </router-link>
        <router-link to="/admin/field-options" class="module-link">
          <AIcon name="list" />
          <span>选项配置</span>
        </router-link>
        <router-link to="/admin/settings" class="module-link">
          <AIcon name="system-setting" />
          <span>主题设置</span>
        </router-link>
        <router-link to="/admin/users" class="module-link">
          <AIcon name="usergroup" />
          <span>用户管理</span>
        </router-link>
        <router-link to="/admin/operation-logs" class="module-link">
          <AIcon name="file-paste" />
          <span>操作记录</span>
        </router-link>
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
          <router-link v-if="authStore.isAdmin" to="/admin" class="sidebar-action">
            <AIcon name="setting" />
            <span>后台</span>
          </router-link>
          <button v-if="authStore.isAuthenticated" type="button" class="sidebar-action" @click="logout">
            <AIcon name="rollback" />
            <span>退出登录</span>
          </button>
          <button v-else type="button" class="sidebar-action" @click="router.push('/login')">
            <AIcon name="user" />
            <span>登录系统</span>
          </button>
        </div>
        <div class="system-status">
          <span />
          <strong>系统可用</strong>
          <em>数据已同步</em>
        </div>
      </div>
    </aside>

    <section class="system-main">
      <main class="system-content">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from '@/ui/message'
import { useAuthStore } from '@/store/auth'
import brandLogo from '@/assets/aoqiang-construction-logo.svg'

const router = useRouter()
const authStore = useAuthStore()
type SidebarMode = 'full' | 'icon' | 'hidden'
const SIDEBAR_MODE_KEY = 'jiqing-sidebar-mode'
const sidebarMode = ref<SidebarMode>('full')

const mainNav = [
  { path: '/', label: '首页数据看板', icon: 'dashboard', badge: 'LIVE' },
  { path: '/project-management', label: '项目管理', icon: 'task', badge: '已启用' },
  { path: '/materials', label: '资料中心', icon: 'folder', badge: '已启用' },
  { path: '/audit', label: '审计看板', icon: 'view-module', badge: '已启用' },
  { path: '/bidding', label: '招投标看板', icon: 'file-paste', badge: '建设中' },
  { path: '/finance', label: '财务看板', icon: 'list', badge: '建设中' },
]

function setSidebarMode(mode: SidebarMode) {
  sidebarMode.value = mode
}

onMounted(() => {
  const saved = window.localStorage.getItem(SIDEBAR_MODE_KEY)
  if (saved === 'full' || saved === 'icon' || saved === 'hidden') {
    sidebarMode.value = saved
  }
})

watch(sidebarMode, (mode) => {
  window.localStorage.setItem(SIDEBAR_MODE_KEY, mode)
})

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
  grid-template-columns: 240px minmax(0, 1fr);
  background: var(--bg-page);
  color: var(--text-primary);
}

.system-shell--icon {
  grid-template-columns: 76px minmax(0, 1fr);
}

.system-shell--hidden {
  grid-template-columns: minmax(0, 1fr);
}

.system-sidebar {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-3);
  background: var(--bg-surface);
  border-right: 1px solid var(--border-color);
  color: var(--text-primary);
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
  min-height: 178px;
  padding: var(--space-2) var(--space-2) var(--space-4);
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

.brand-copy { display: grid; gap: 3px; padding-left: 1px; }
.system-brand strong { font-size: var(--text-md); font-weight: 700; }
.system-brand em { color: var(--text-tertiary); font-size: 11px; }

.system-shell--icon .system-sidebar {
  gap: var(--space-3);
  padding: var(--space-3) var(--space-2);
}

.system-shell--icon .system-brand {
  min-height: 64px;
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
  color: var(--text-tertiary);
  font-size: 10px;
}

.module-link--active small {
  color: var(--color-brand-500);
}

.module-link--disabled {
  opacity: .78;
}

.sidebar-foot {
  display: grid;
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-color);
}

.sidebar-actions {
  display: grid;
  gap: var(--space-2);
}

.sidebar-collapse-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-1);
}

.sidebar-collapse-actions button {
  min-width: 0;
  min-height: 30px;
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
  min-height: 36px;
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
  padding: var(--space-3);
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
}

.system-status strong { font-size: var(--text-xs); font-weight: 600; }
.system-status em { font-size: 10px; font-style: normal; color: var(--text-tertiary); }

.system-main {
  min-width: 0;
  min-height: 100vh;
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
  .system-shell { grid-template-columns: 72px minmax(0, 1fr); }
  .system-shell--hidden { grid-template-columns: minmax(0, 1fr); }
  .system-sidebar { padding: var(--space-3) var(--space-2); gap: var(--space-3); }
  .system-brand .brand-copy,
  .module-link span,
  .module-link small,
  .nav-group p,
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
  .system-shell { grid-template-columns: 1fr; }
  .system-shell--hidden { grid-template-columns: minmax(0, 1fr); }
  .system-sidebar {
    position: sticky;
    top: 0;
    z-index: 20;
    min-height: auto;
    grid-template-columns: auto 1fr;
    grid-template-rows: auto auto;
    gap: var(--space-3);
    padding: var(--space-3);
  }
  .system-brand span:not(.brand-icon) { display: block; }
  .system-brand {
    min-height: 170px;
    max-width: 240px;
  }
  .brand-icon {
    width: 188px;
    height: 142px;
    justify-items: start;
  }
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
  .module-link span,
  .module-link small {
    display: inline;
  }
  .module-link small {
    margin-left: auto;
  }
  .nav-group,
  .sidebar-foot { display: none; }
  .system-main { min-height: auto; }
}
</style>

