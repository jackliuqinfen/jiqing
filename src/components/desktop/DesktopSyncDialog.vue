<template>
  <AModal
    :visible="visible"
    class="desktop-sync-dialog"
    header="本地资料同步"
    width="920px"
    :footer="false"
    :confirm-btn="null"
    :mask-closable="false"
    @update:visible="updateVisible"
    @cancel="updateVisible(false)"
  >
    <div class="sync-dialog-body">
      <header class="sync-header">
        <div>
          <p class="sync-eyebrow">服务器到本地只读同步</p>
          <h3>{{ statusLabel }}</h3>
          <p>{{ state?.message || '同步状态正在读取' }}</p>
        </div>
        <div class="client-meta" aria-label="桌面客户端信息">
          <span>{{ releaseLabel }}</span>
          <strong>v{{ capabilities?.clientVersion || '—' }}</strong>
        </div>
      </header>

      <AAlert v-if="permissionMessage" :type="permissionRefreshRequired ? 'warning' : 'info'" show-icon>
        {{ permissionMessage }}
      </AAlert>
      <AAlert v-if="errorMessage" type="error" show-icon>
        {{ errorMessage }}
      </AAlert>

      <section v-if="policyDisabled || state?.status === 'disabled'" class="sync-empty">
        <AIcon name="lock-on" size="28" />
        <strong>当前账号未启用本地资料同步</strong>
        <p>请联系管理员在后台同步策略中授权，授权完成后重新打开本窗口。</p>
      </section>

      <template v-else>
        <section class="sync-section">
          <div class="section-head">
            <div>
              <h4>本地文件夹</h4>
              <p>服务器文件会写入下方目录，本地改动不会回传服务器。</p>
            </div>
            <AButton variant="outline" :disabled="actionPending || isSyncing || startPending" @click="chooseFolder">
              <template #icon><AIcon name="folder" /></template>
              选择本地文件夹
            </AButton>
          </div>
          <div class="folder-path" :class="{ 'folder-path--empty': !state?.localRoot }">
            {{ state?.localRoot || '尚未选择本地文件夹' }}
          </div>
        </section>

        <section class="sync-section">
          <div class="section-head">
            <div>
              <h4>同步项目</h4>
              <p>仅显示服务器判定当前账号有权访问的真实项目。</p>
            </div>
            <AButton
              v-if="permissionRefreshRequired"
              variant="outline"
              :loading="loadingProjects"
              @click="refreshPolicy"
            >
              <template #icon><AIcon name="refresh" /></template>
              重新检查权限
            </AButton>
          </div>
          <ASelect
            v-model="selectedProjectRefs"
            multiple
            allow-search
            allow-clear
            :loading="loadingProjects"
            :disabled="projectSelectionDisabled"
            :options="projectOptions"
            aria-label="选择需要同步的项目"
            placeholder="搜索并选择需要同步的项目"
          />
          <p v-if="!loadingProjects && !projects.length && !permissionRefreshRequired && !errorMessage" class="empty-hint">
            当前没有可同步项目。
          </p>
          <div class="selection-summary">
            <span>已选 {{ selectedTotals.projects }} 个项目</span>
            <span>{{ selectedTotals.files }} 个文件</span>
            <span>{{ formatBytes(selectedTotals.bytes) }}</span>
          </div>
        </section>

        <section class="sync-section sync-progress" aria-live="polite">
          <div class="section-head">
            <div>
              <h4>同步进度</h4>
              <p>最后成功：{{ formatDateTime(state?.lastSuccessAt) }}</p>
            </div>
            <strong>{{ progressPercent }}%</strong>
          </div>
          <div class="progress-track" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100">
            <span :style="{ width: `${progressPercent}%` }" />
          </div>
          <div class="progress-stats">
            <span>已同步 {{ state?.completedFiles || 0 }} / {{ state?.totalFiles || 0 }}</span>
            <span>已下载 {{ formatBytes(state?.bytesDownloaded || 0) }}</span>
            <span :class="{ 'failed-count': (state?.failedFiles || 0) > 0 }">失败 {{ state?.failedFiles || 0 }}</span>
          </div>
          <details v-if="(state?.failedFiles || 0) > 0" class="failure-summary">
            <summary>查看失败说明</summary>
            <p>{{ state?.message || `有 ${state?.failedFiles || 0} 个文件未完成同步，请稍后重试。` }}</p>
          </details>
        </section>
      </template>

      <AAlert type="warning" show-icon class="readonly-warning">
        本地新增或修改不会自动上传。服务器始终是业务资料的唯一权威来源。
      </AAlert>

      <footer class="sync-actions">
        <AButton variant="outline" @click="updateVisible(false)">关闭</AButton>
        <AButton
          variant="outline"
          :disabled="!state?.localRoot || actionPending"
          @click="openFolder"
        >
          打开本地文件夹
        </AButton>
        <AButton
          variant="outline"
          :disabled="(!isSyncing && !startPending) || actionPending"
          @click="pause"
        >
          暂停同步
        </AButton>
        <AButton
          theme="primary"
          :loading="isSyncing || startPending"
          :disabled="!canStart"
          @click="start"
        >
          立即同步
        </AButton>
      </footer>
    </div>
  </AModal>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import { useDesktopSync } from '@/composables/useDesktopSync'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()

const {
  capabilities,
  state,
  projects,
  selectedProjectRefs,
  loadingProjects,
  actionPending,
  startPending,
  errorMessage,
  permissionMessage,
  permissionRefreshRequired,
  policyDisabled,
  isSyncing,
  projectSelectionDisabled,
  canStart,
  setDialogOpen,
  refreshPolicy,
  chooseFolder,
  start,
  pause,
  openFolder,
} = useDesktopSync()

const statusLabels: Record<string, string> = {
  disabled: '同步未启用',
  waiting_for_login: '等待重新登录',
  checking_policy: '正在检查权限',
  syncing: '正在同步',
  paused: '同步已暂停',
  completed: '同步已完成',
  partial_failure: '部分文件未完成',
  permission_changed: '权限范围已变化',
  offline: '服务器暂时不可达',
}

const statusLabel = computed(() => statusLabels[state.value?.status || ''] || '同步准备中')
const releaseLabel = computed(() => ({
  development: '开发环境',
  'internal-test': '内部测试',
  production: '正式环境',
}[capabilities.value?.releaseChannel || 'development']))
const projectOptions = computed(() => projects.value.map((project) => ({
  label: project.projectCode
    ? `${project.projectName}（${project.projectCode}） · ${project.fileCount} 个文件`
    : `${project.projectName} · ${project.fileCount} 个文件`,
  value: project.projectRef,
})))
const selectedTotals = computed(() => {
  const selected = new Set(selectedProjectRefs.value)
  return projects.value.reduce((total, project) => {
    if (!selected.has(project.projectRef)) return total
    total.projects += 1
    total.files += project.fileCount
    total.bytes += project.totalFileSizeBytes
    return total
  }, { projects: 0, files: 0, bytes: 0 })
})
const progressPercent = computed(() => {
  const total = state.value?.totalFiles || 0
  if (!total) return 0
  return Math.min(100, Math.round(((state.value?.completedFiles || 0) / total) * 100))
})

function updateVisible(value: boolean) {
  if (!value) void setDialogOpen(false)
  emit('update:visible', value)
}

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function formatDateTime(value?: string) {
  if (!value) return '尚无成功记录'
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return '尚无成功记录'
  return new Date(timestamp).toLocaleString('zh-CN', { hour12: false })
}

watch(
  () => props.visible,
  (visible) => {
    void setDialogOpen(visible)
  },
)

onMounted(() => {
  void setDialogOpen(props.visible)
})
</script>

<style scoped>
.sync-dialog-body {
  display: grid;
  gap: 16px;
}

.sync-header,
.section-head,
.sync-actions,
.progress-stats,
.selection-summary {
  display: flex;
  align-items: center;
}

.sync-header,
.section-head {
  justify-content: space-between;
  gap: 20px;
}

.sync-header {
  padding: 2px 0 14px;
  border-bottom: 1px solid var(--border-color);
}

.sync-eyebrow {
  color: var(--color-brand-600);
  font-size: 12px;
  font-weight: 600;
}

.sync-header h3,
.sync-section h4,
.sync-header p,
.sync-section p {
  margin: 0;
}

.sync-header h3 {
  margin: 4px 0;
  color: var(--text-primary);
  font-size: 20px;
}

.sync-header p,
.sync-section p,
.empty-hint {
  color: var(--text-secondary);
  font-size: 13px;
}

.client-meta {
  display: grid;
  gap: 3px;
  min-width: 104px;
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  text-align: right;
}

.client-meta span {
  color: var(--text-tertiary);
  font-size: 11px;
}

.client-meta strong {
  color: var(--text-primary);
  font-size: 13px;
}

.sync-section {
  display: grid;
  gap: 12px;
  padding: 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.sync-section h4 {
  margin-bottom: 3px;
  color: var(--text-primary);
  font-size: 14px;
}

.folder-path {
  overflow: hidden;
  padding: 10px 12px;
  color: var(--text-primary);
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-path--empty,
.empty-hint {
  color: var(--text-tertiary);
}

.selection-summary,
.progress-stats {
  flex-wrap: wrap;
  gap: 8px 18px;
  color: var(--text-secondary);
  font-size: 12px;
}

.progress-track {
  height: 8px;
  overflow: hidden;
  background: var(--bg-page);
  border-radius: 4px;
}

.progress-track span {
  display: block;
  height: 100%;
  background: var(--color-brand-500);
  border-radius: 4px;
  transition: width 180ms ease;
}

.failed-count {
  color: var(--color-danger);
}

.failure-summary {
  padding-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.failure-summary summary {
  color: var(--color-danger);
  cursor: pointer;
}

.failure-summary p {
  margin-top: 8px;
}

.sync-empty {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 180px;
  padding: 24px;
  color: var(--text-secondary);
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  text-align: center;
}

.sync-empty strong {
  color: var(--text-primary);
}

.sync-empty p {
  margin: 0;
  font-size: 13px;
}

.readonly-warning {
  border-radius: 8px;
}

.sync-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}

:deep(.arco-select-view) {
  min-height: 38px;
  border-radius: 6px;
}

@media (max-width: 720px) {
  .sync-header,
  .section-head {
    align-items: stretch;
    flex-direction: column;
  }

  .client-meta {
    text-align: left;
  }

  .sync-actions {
    align-items: stretch;
    flex-direction: column-reverse;
  }
}
</style>
