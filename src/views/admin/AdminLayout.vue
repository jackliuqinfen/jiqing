<template>
  <div class="admin-layout">
    <!-- 侧边栏 — 纯白 + 1px 右边框 -->
    <aside class="admin-sidebar">
      <div class="sidebar-header">
        <div class="sidebar-logo">
          <t-icon name="setting" size="18px" />
        </div>
        <div class="sidebar-brand">
          <span class="sidebar-title">系统管理</span>
          <span class="sidebar-subtitle">Admin Console</span>
        </div>
      </div>

      <nav class="sidebar-nav" role="navigation">
        <router-link to="/admin" class="nav-item" exact-active-class="nav-item--active">
          <t-icon name="dashboard" />
          <span>仪表盘</span>
        </router-link>
        <router-link to="/admin/users" class="nav-item" active-class="nav-item--active">
          <t-icon name="usergroup" />
          <span>用户管理</span>
        </router-link>
        <router-link to="/admin/field-configs" class="nav-item" active-class="nav-item--active">
          <t-icon name="edit-1" />
          <span>字段配置</span>
        </router-link>
        <router-link to="/admin/field-options" class="nav-item" active-class="nav-item--active">
          <t-icon name="list" />
          <span>选项库</span>
        </router-link>
        <router-link to="/admin/settings" class="nav-item" active-class="nav-item--active">
          <t-icon name="system-setting" />
          <span>系统设置</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <router-link to="/" class="nav-item nav-item--back">
          <t-icon name="rollback" />
          <span>返回看板</span>
        </router-link>
        <div class="sidebar-user">
          <t-avatar size="small" :style="{ background: 'var(--color-brand-500)' }">
            {{ userInitials }}
          </t-avatar>
          <div class="sidebar-user-info">
            <span class="sidebar-user-name">{{ authStore.displayName }}</span>
            <span class="sidebar-user-role">管理员</span>
          </div>
        </div>
      </div>
    </aside>

    <main class="admin-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import { getInitials } from '@/utils/format'

const authStore = useAuthStore()
const userInitials = computed(() => getInitials(authStore.displayName))
</script>

<style scoped>
.admin-layout {
  display: flex;
  height: 100vh;
  background: var(--bg-page);
}

/* 侧边栏 — 纯白 + 实线边框 */
.admin-sidebar {
  width: 240px;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-color-strong);
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-4);
  border-bottom: 1px solid var(--border-color);
}

.sidebar-logo {
  width: 34px; height: 34px;
  background: var(--color-brand-500);
  color: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-brand { display: flex; flex-direction: column; gap: 1px; }

.sidebar-title {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-subtitle {
  font-size: 10px;
  color: var(--text-tertiary);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

/* 导航 */
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: var(--space-3) var(--space-2);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 8px var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  text-decoration: none;
  transition: all var(--duration-fast);
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item--active {
  background: var(--color-brand-50);
  color: var(--color-brand-500);
  font-weight: 500;
}

.nav-item--active:hover {
  background: var(--color-brand-50);
  color: var(--color-brand-500);
}

/* 底部 */
.sidebar-footer {
  padding: var(--space-3) var(--space-2);
  border-top: 1px solid var(--border-color);
}

.nav-item--back {
  margin-bottom: var(--space-3);
  font-size: var(--text-xs);
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-2);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.sidebar-user-info { display: flex; flex-direction: column; min-width: 0; }
.sidebar-user-name { font-size: var(--text-xs); font-weight: 500; color: var(--text-primary); }
.sidebar-user-role { font-size: 10px; color: var(--text-tertiary); }

/* 主区 */
.admin-main {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
}

@media (max-width: 768px) {
  .admin-sidebar { width: 64px; }
  .sidebar-brand, .nav-item span, .sidebar-user-info, .sidebar-subtitle { display: none; }
  .nav-item { justify-content: center; padding: 10px; }
  .admin-main { padding: var(--space-4); }
}
</style>
