<template>
  <div class="system-shell">
    <aside class="system-sidebar">
      <router-link to="/" class="system-brand" aria-label="江苏集庆·工程管理系统">
        <span class="brand-icon"><img :src="brandLogo" alt="" /></span>
        <span>
          <strong>江苏集庆</strong>
          <em>工程管理系统</em>
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
          <t-icon :name="item.icon" />
          <span>{{ item.label }}</span>
          <small v-if="item.badge">{{ item.badge }}</small>
        </router-link>
      </nav>

      <div class="nav-group">
        <p>后台管理</p>
        <router-link v-if="authStore.isAdmin" to="/admin/field-configs" class="module-link">
          <t-icon name="edit-1" />
          <span>字段配置</span>
        </router-link>
        <router-link v-if="authStore.isAdmin" to="/admin/field-options" class="module-link">
          <t-icon name="list" />
          <span>内容库管理</span>
        </router-link>
        <router-link v-if="authStore.isAdmin" to="/admin/settings" class="module-link">
          <t-icon name="system-setting" />
          <span>主题设置</span>
        </router-link>
        <router-link v-if="authStore.isAdmin" to="/admin/users" class="module-link">
          <t-icon name="usergroup" />
          <span>用户管理</span>
        </router-link>
        <router-link v-if="authStore.isAdmin" to="/admin/operation-logs" class="module-link">
          <t-icon name="file-paste" />
          <span>操作日志</span>
        </router-link>
      </div>

      <div class="sidebar-foot">
        <div class="system-status">
          <span />
          <strong>生产环境</strong>
          <em>SQLite · Arco</em>
        </div>
      </div>
    </aside>

    <section class="system-main">
      <header class="system-topbar">
        <div>
          <h1>{{ routeTitle }}</h1>
          <p>{{ routeSubtitle }}</p>
        </div>
        <div class="topbar-actions">
          <t-button v-if="authStore.isAdmin" variant="outline" size="small" @click="router.push('/admin')">
            <template #icon><t-icon name="setting" /></template>
            后台
          </t-button>
          <t-button v-if="authStore.isAuthenticated" variant="text" size="small" @click="logout">退出</t-button>
          <t-button v-else theme="primary" size="small" @click="router.push('/login')">登录</t-button>
        </div>
      </header>
      <main class="system-content">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { MessagePlugin } from '@/ui/message'
import { useAuthStore } from '@/store/auth'
import brandLogo from '@/assets/aoqiang-construction-logo.svg'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const mainNav = [
  { path: '/', label: '首页数据看板', icon: 'dashboard', badge: 'LIVE' },
  { path: '/audit', label: '审计看板', icon: 'view-module', badge: '已启用' },
  { path: '/project-management', label: '项目管理', icon: 'task', badge: '建设中' },
  { path: '/bidding', label: '招投标看板', icon: 'file-paste', badge: '建设中' },
  { path: '/finance', label: '财务看板', icon: 'list', badge: '建设中' },
]

const routeTitle = computed(() => String(route.meta.title || '江苏集庆·工程管理系统'))
const routeSubtitle = computed(() => String(route.meta.subtitle || '稳态指挥台 · 工程经营与审计协同'))

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
  grid-template-columns: 252px minmax(0, 1fr);
  background:
    linear-gradient(180deg, rgba(22, 93, 255, .05), transparent 280px),
    var(--bg-page);
  color: var(--text-primary);
}

.system-sidebar {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: var(--space-4);
  padding: var(--space-4);
  background:
    linear-gradient(180deg, #0b1a33 0%, #0f1f3d 54%, #0b1628 100%);
  border-right: 1px solid rgba(255, 255, 255, .08);
  color: #fff;
}

.system-brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 56px;
  color: #fff;
  text-decoration: none;
}

.brand-icon {
  width: 46px;
  height: 38px;
  display: grid;
  place-items: center;
  padding: 4px 6px;
  background: rgba(255, 255, 255, .96);
  border: 1px solid rgba(255, 255, 255, .16);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .12);
  overflow: hidden;
}

.brand-icon img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.system-brand strong,
.system-brand em {
  display: block;
  font-style: normal;
  line-height: 1.25;
}

.system-brand strong { font-size: var(--text-lg); font-weight: 700; }
.system-brand em { color: rgba(255, 255, 255, .62); font-size: var(--text-xs); }

.module-nav,
.nav-group {
  display: grid;
  gap: 6px;
}

.nav-group {
  align-self: start;
  padding-top: var(--space-3);
  border-top: 1px solid rgba(255, 255, 255, .1);
}

.nav-group p {
  margin: 0 0 var(--space-1);
  padding: 0 var(--space-3);
  color: rgba(255, 255, 255, .42);
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
  background: transparent;
  color: rgba(255, 255, 255, .76);
  cursor: pointer;
  font: inherit;
  text-align: left;
  text-decoration: none;
}

.module-link:hover,
.module-link--active {
  background: rgba(22, 93, 255, .22);
  border-color: rgba(20, 201, 201, .34);
  color: #fff;
}

.module-link :deep(.t-icon) { flex: 0 0 auto; }
.module-link span { flex: 1; min-width: 0; }
.module-link small {
  color: rgba(255, 255, 255, .54);
  font-size: 10px;
}

.module-link--disabled {
  opacity: .78;
}

.sidebar-foot {
  padding-top: var(--space-4);
  border-top: 1px solid rgba(255, 255, 255, .1);
}

.system-status {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 2px 8px;
  align-items: center;
  color: rgba(255, 255, 255, .72);
}

.system-status span {
  width: 8px;
  height: 8px;
  grid-row: span 2;
  background: var(--color-success);
}

.system-status strong { font-size: var(--text-xs); font-weight: 600; }
.system-status em { font-size: 10px; font-style: normal; color: rgba(255, 255, 255, .45); }

.system-main {
  min-width: 0;
  min-height: 100vh;
  display: grid;
  grid-template-rows: 64px minmax(0, 1fr);
}

.system-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 0 var(--space-6);
  background: rgba(255, 255, 255, .94);
  border-bottom: 1px solid var(--border-color);
}

.system-topbar h1 {
  margin: 0;
  font-size: var(--text-xl);
  line-height: 1.25;
}

.system-topbar p {
  margin: 3px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.system-content {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: var(--space-5);
}

@media (max-width: 900px) {
  .system-shell { grid-template-columns: 72px minmax(0, 1fr); }
  .system-sidebar { padding: var(--space-3) var(--space-2); }
  .system-brand span:not(.brand-icon),
  .module-link span,
  .module-link small,
  .nav-group p,
  .system-status strong,
  .system-status em { display: none; }
  .brand-icon {
    width: 42px;
    height: 34px;
    padding: 4px;
  }
  .module-link { justify-content: center; padding: 0; min-height: 42px; }
  .system-content { padding: var(--space-3); }
}

@media (max-width: 640px) {
  .system-shell { grid-template-columns: 1fr; }
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
    min-height: 44px;
    max-width: 240px;
  }
  .brand-icon {
    width: 48px;
    height: 40px;
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
  .system-main { min-height: auto; grid-template-rows: auto minmax(0, 1fr); }
  .system-topbar {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--space-3);
  }
  .system-topbar h1 { font-size: var(--text-lg); }
  .system-topbar p { max-width: 100%; }
  .topbar-actions { width: 100%; justify-content: flex-end; }
}
</style>
