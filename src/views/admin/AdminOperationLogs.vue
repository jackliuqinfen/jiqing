<template>
  <div class="operation-logs">
    <PageHeader title="操作记录" description="查看账号登录、项目资料、主题设置和管理配置等关键操作。">
      <template #meta>
        <ATag variant="light" theme="primary">共 {{ filteredLogs.length }} 条</ATag>
        <ATag v-if="keyword || resultFilter || roleFilter" variant="light">已应用筛选</ATag>
      </template>
      <template #actions>
        <AButton variant="outline" :loading="loading" @click="fetchLogs">
          <template #icon><AIcon name="refresh" /></template>
          刷新
        </AButton>
      </template>
    </PageHeader>

    <div class="log-toolbar">
      <AInput v-model="keyword" placeholder="搜索账号、操作内容或对象" clearable :style="{ width: '280px' }">
        <template #prefix-icon><AIcon name="search" /></template>
      </AInput>
      <ASelect
        v-model="resultFilter"
        placeholder="结果"
        clearable
        :style="{ width: '120px' }"
        :options="resultOptions"
      />
      <ASelect
        v-model="roleFilter"
        placeholder="角色"
        clearable
        :style="{ width: '130px' }"
        :options="roleOptions"
      />
      <span class="log-count">共 {{ filteredLogs.length }} 条</span>
    </div>

    <StatePanel
      v-if="loading && logs.length === 0"
      state="loading"
      title="正在读取操作记录"
      description="正在整理登录、项目、附件和配置记录，请稍候。"
    />

    <StatePanel
      v-else-if="fetchError"
      state="error"
      title="操作记录加载失败"
      description="记录列表暂时没有读取成功，可能是网络异常或服务响应较慢。你可以重试，必要时联系管理员。"
    >
      <template #actions>
        <AButton theme="primary" :loading="loading" @click="fetchLogs">
          <template #icon><AIcon name="refresh" /></template>
          重新加载
        </AButton>
      </template>
    </StatePanel>

    <StatePanel
      v-else-if="filteredLogs.length === 0"
      state="empty"
      title="未找到符合条件的记录"
      :description="keyword || resultFilter || roleFilter ? '请调整筛选条件后再试，或清除筛选查看全部记录。' : '当前还没有操作记录。'"
    >
      <template #actions>
        <AButton v-if="keyword || resultFilter || roleFilter" variant="outline" @click="resetFilters">清除筛选</AButton>
        <AButton theme="primary" :loading="loading" @click="fetchLogs">
          <template #icon><AIcon name="refresh" /></template>
          重新加载
        </AButton>
      </template>
    </StatePanel>

    <ATable
      v-else
      :data="filteredLogs"
      :columns="tableColumns"
      row-key="id"
      :loading="loading"
      :bordered="true"
      hover
      size="medium"
    >
      <template #createdAt="{ row }">
        <span class="date-cell">{{ formatDateTime(row.createdAt) }}</span>
      </template>
      <template #username="{ row }">
        <div class="user-cell">
          <strong>{{ row.username || '系统' }}</strong>
          <span>{{ roleLabel(row.role) }}</span>
        </div>
      </template>
      <template #action="{ row }">
        <ATag :theme="actionTheme(row.action)" variant="light" size="small">
          {{ actionLabel(row.action) }}
        </ATag>
      </template>
      <template #target="{ row }">
        <div class="target-cell">
          <strong>{{ targetLabel(row.targetType) }}</strong>
          <span>{{ row.targetId || '—' }}</span>
        </div>
      </template>
      <template #result="{ row }">
        <ATag :theme="row.result === 'success' ? 'success' : 'danger'" variant="light" size="small">
          {{ row.result === 'success' ? '成功' : '失败' }}
        </ATag>
      </template>
      <template #ipAddress="{ row }">
        <span class="mono-cell">{{ row.ipAddress || '—' }}</span>
      </template>
      <template #detail="{ row }">
        <span class="detail-cell" :title="detailText(row.detail)">{{ detailText(row.detail) }}</span>
      </template>
    </ATable>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getOperationLogs } from '@/api/system'
import { MessagePlugin } from '@/ui/message'
import type { AdminRole, OperationLogEntry } from '@/types'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'

const tableColumns = [
  { colKey: 'createdAt', title: '时间', width: 160 },
  { colKey: 'username', title: '操作人', width: 150 },
  { colKey: 'action', title: '动作', width: 150 },
  { colKey: 'target', title: '对象', ellipsis: true },
  { colKey: 'result', title: '结果', width: 90 },
  { colKey: 'ipAddress', title: '登录位置', width: 130 },
  { colKey: 'detail', title: '详情', ellipsis: true },
]

const resultOptions = [
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

const roleOptions = [
  { label: '管理员', value: 'admin' },
  { label: '编辑者', value: 'editor' },
  { label: '查看者', value: 'viewer' },
  { label: '系统', value: 'system' },
]

const logs = ref<OperationLogEntry[]>([])
const loading = ref(false)
const fetchError = ref('')
const keyword = ref('')
const resultFilter = ref('')
const roleFilter = ref<AdminRole | 'system' | ''>('')

const filteredLogs = computed(() => {
  let list = logs.value
  const kw = keyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((log) =>
      [
        log.username,
        roleLabel(log.role),
        log.action,
        actionLabel(log.action),
        log.targetType,
        targetLabel(log.targetType),
        log.targetId,
        log.ipAddress,
        detailText(log.detail),
      ]
        .join(' ')
        .toLowerCase()
        .includes(kw)
    )
  }
  if (resultFilter.value) list = list.filter((log) => log.result === resultFilter.value)
  if (roleFilter.value) {
    list = list.filter((log) => (roleFilter.value === 'system' ? !log.role : log.role === roleFilter.value))
  }
  return list
})

function roleLabel(role: AdminRole | '') {
  return { admin: '管理员', editor: '编辑者', viewer: '查看者', '': '系统' }[role] || role
}

function actionLabel(action: string) {
  const labels: Record<string, string> = {
    'auth.login_success': '登录成功',
    'auth.login_failed': '登录失败',
    'auth.logout': '退出登录',
    'project.create': '项目创建',
    'project.update': '项目更新',
    'project.progress': '进度调整',
    'project_record.create': '创建项目主档案',
    'project_record.update': '更新项目主档案',
    'project_record.delete': '删除项目主档案',
    'project.audit.start': '发起审计流程',
    'project_file.upload': '上传项目资料',
    'project_file.rename': '重命名项目资料',
    'project_file.delete': '删除项目资料',
    'project_settlement.create': '新增结算记录',
    'project_settlement.update': '更新结算记录',
    'project_settlement.delete': '删除结算记录',
    'project_variation.create': '新增变更签证',
    'project_variation.update': '更新变更签证',
    'project_variation.delete': '删除变更签证',
    'attachment.upload': '附件上传',
    'attachment.delete': '附件删除',
    'theme.update': '主题更新',
    'system.setting_update': '系统设置',
    'user.create': '用户创建',
    'user.update': '用户更新',
    'field_config.upsert': '字段配置',
    'field_config.delete': '字段删除',
    'field_option.upsert': '选项配置',
    'field_option.delete': '选项删除',
  }
  return labels[action] || '业务操作'
}

function actionTheme(action: string) {
  if (action.includes('failed') || action.includes('delete')) return 'danger'
  if (action.includes('attachment')) return 'warning'
  if (action.includes('theme') || action.includes('setting')) return 'primary'
  if (action.includes('login')) return 'success'
  return 'default'
}

function targetLabel(targetType: string) {
  const labels: Record<string, string> = {
    system_user: '用户',
    audit_project: '审计项目',
    audit_project_attachment: '项目附件',
    project_record: '项目主档案',
    project_file: '项目资料',
    project_settlement: '结算记录',
    project_variation: '变更签证',
    system_theme: '主题',
    system_setting: '系统设置',
    audit_field_config: '字段配置',
    audit_field_option: '选项库',
  }
  return labels[targetType] || '业务对象'
}

function detailText(detail: Record<string, unknown>) {
  const entries = Object.entries(detail || {}).filter(([, value]) => value !== undefined && value !== null && value !== '')
  if (!entries.length) return '—'
  return entries.map(([key, value]) => `${detailKeyLabel(key)}: ${String(value)}`).join('；')
}

function detailKeyLabel(key: string) {
  const labels: Record<string, string> = {
    action: '操作内容',
    targetId: '关联对象',
    target_id: '关联对象',
    username: '账号',
    role: '角色',
    result: '结果',
    message: '说明',
    reason: '原因',
    theme: '主题',
    projectId: '项目',
    project_id: '项目',
    fileName: '文件名称',
    file_name: '文件名称',
  }
  return labels[key] || '记录项'
}

function resetFilters() {
  keyword.value = ''
  resultFilter.value = ''
  roleFilter.value = ''
}

function formatDateTime(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function fetchLogs() {
  loading.value = true
  fetchError.value = ''
  try {
    logs.value = await getOperationLogs()
  } catch (err) {
    fetchError.value = err instanceof Error ? err.message : '操作记录加载失败'
    MessagePlugin.error(fetchError.value)
  } finally {
    loading.value = false
  }
}

onMounted(fetchLogs)
</script>

<style scoped>
.operation-logs { max-width: 1280px; }

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.page-header-left { min-width: 0; }
.page-title { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); margin: 0 0 var(--space-1); }
.page-desc { font-size: var(--text-sm); color: var(--text-secondary); margin: 0; }

.log-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.log-count { margin-left: auto; font-size: var(--text-xs); color: var(--text-tertiary); }

.user-cell,
.target-cell {
  display: grid;
  gap: 2px;
}

.user-cell strong,
.target-cell strong {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: 600;
}

.user-cell span,
.target-cell span,
.date-cell,
.detail-cell {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.mono-cell {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.detail-cell {
  display: inline-block;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 880px) {
  .page-header,
  .log-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .log-count { margin-left: 0; }
}
</style>

