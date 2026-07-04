<template>
  <div class="admin-dashboard">
    <PageHeader title="管理工作台" description="集中管理账号、资料、字段、主题和操作记录。">
      <template #meta>
        <ATag variant="light" theme="primary">管理概览</ATag>
      </template>
      <template #actions>
        <AButton variant="outline" :loading="loading" @click="loadDashboard">
          <template #icon><AIcon name="refresh" /></template>
          刷新
        </AButton>
      </template>
    </PageHeader>

    <StatePanel
      v-if="loading && !loaded"
      state="loading"
      title="正在读取管理概览"
      description="正在汇总账号、项目和配置数据，请稍候。"
    />

    <StatePanel
      v-else-if="loadError"
      state="error"
      title="管理概览加载失败"
      description="概览数据暂时没能读取成功，可能是网络波动。你可以重试，或稍后再看。"
    >
      <template #actions>
        <AButton theme="primary" :loading="loading" @click="loadDashboard">
          <template #icon><AIcon name="refresh" /></template>
          重新加载
        </AButton>
      </template>
    </StatePanel>

    <template v-else>
      <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon" style="background:var(--color-brand-50);color:var(--color-brand-500)">
          <AIcon name="usergroup" size="22px" />
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.totalUsers }}</span>
          <span class="stat-label">总用户数</span>
          <span class="stat-sub">活跃 {{ stats.activeUsers }} 人</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background:var(--color-success-bg);color:var(--color-success)">
          <AIcon name="user-checked" size="22px" />
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.adminCount }}</span>
          <span class="stat-label">管理员</span>
          <span class="stat-sub">拥有后台权限</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background:var(--color-warning-bg);color:var(--color-warning)">
          <AIcon name="file-paste" size="22px" />
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.totalProjects }}</span>
          <span class="stat-label">结算项目</span>
          <span class="stat-sub">全量业务数据</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" style="background:var(--color-info-bg);color:var(--color-info)">
          <AIcon name="setting" size="22px" />
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ settingsCount }}</span>
          <span class="stat-label">管理配置</span>
          <span class="stat-sub">主题、字段和规则</span>
        </div>
      </div>
      </div>

      <div class="quick-actions">
        <h3 class="section-title">快捷入口</h3>
        <div class="actions-grid">
        <router-link to="/admin/users" class="action-card">
          <AIcon name="user-add" size="22px" />
          <span class="action-title">用户管理</span>
          <span class="action-desc">添加、编辑、停用账号</span>
        </router-link>
        <router-link to="/admin/settings" class="action-card">
          <AIcon name="system-setting" size="22px" />
          <span class="action-title">基础设置</span>
          <span class="action-desc">维护登录、主题和品牌配置</span>
        </router-link>
        <router-link to="/materials" class="action-card">
          <AIcon name="folder" size="22px" />
          <span class="action-title">资料中心</span>
          <span class="action-desc">按项目和类型归集业务资料</span>
        </router-link>
        <router-link to="/" class="action-card">
          <AIcon name="view-module" size="22px" />
          <span class="action-title">进入看板</span>
          <span class="action-desc">返回江苏集庆工程管理工作台</span>
        </router-link>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAdminStats, getAllSystemSettings } from '@/api/system'
import type { AdminStats } from '@/types'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'

const stats = ref<AdminStats>({ totalUsers: 0, activeUsers: 0, adminCount: 0, totalProjects: 0, recentLogins: 0 })
const settingsCount = ref(0)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')

async function loadDashboard() {
  loading.value = true
  loadError.value = ''
  try {
    const [s, ss] = await Promise.all([getAdminStats(), getAllSystemSettings()])
    stats.value = s
    settingsCount.value = ss.length
    loaded.value = true
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : '管理概览加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.admin-dashboard { max-width: 960px; }

.page-header { margin-bottom: var(--space-4); }
.page-title { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); margin: 0 0 var(--space-1); }
.page-desc { font-size: var(--text-sm); color: var(--text-secondary); margin: 0; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-10);
}

.stat-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.stat-icon {
  width: 42px; height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-body { display: flex; flex-direction: column; min-width: 0; }
.stat-value { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); line-height: 1.2; }
.stat-label { font-size: var(--text-xs); color: var(--text-secondary); margin-top: 2px; }
.stat-sub { font-size: 11px; color: var(--text-tertiary); margin-top: 2px; }

.section-title { font-size: var(--text-md); font-weight: 600; color: var(--text-primary); margin: 0 0 var(--space-4); }

.actions-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-5);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  text-decoration: none;
  color: var(--text-primary);
  transition: border-color var(--duration-fast);
}

.action-card:hover {
  border-color: var(--color-brand-300);
}

.action-card :deep(.arco-icon) { color: var(--color-brand-500); }
.action-title { font-size: var(--text-sm); font-weight: 600; }
.action-desc { font-size: var(--text-xs); color: var(--text-secondary); }

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .actions-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 620px) {
  .actions-grid { grid-template-columns: 1fr; }
}
</style>

