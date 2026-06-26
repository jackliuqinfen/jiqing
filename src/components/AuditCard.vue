<template>
  <t-card
    :class="cardClasses"
    :bordered="true"
    :shadow="false"
    class="audit-card"
  >
    <!-- 争议标记 — 纯红三角，无阴影 -->
    <div v-if="hasDispute" class="dispute-marker" title="存在结算争议">
      <div class="dispute-triangle" />
    </div>

    <!-- 头部：项目名 + 优先级 + 编号/楼栋 + 分类 -->
    <div class="card-header">
      <div class="project-title-row">
        <t-tooltip :content="item.projectName" placement="top">
          <span class="project-name">{{ item.projectName }}</span>
        </t-tooltip>
        <t-tag :theme="priorityTheme" variant="light-outline" size="small">
          {{ item.priority }}
        </t-tag>
      </div>
      <div class="project-meta">
        <span>{{ item.settlementNo }}</span>
        <span class="meta-sep">|</span>
        <span>{{ item.sectionBuilding }}</span>
      </div>
      <t-tag :theme="categoryTheme" variant="light" size="small" class="category-tag">
        {{ item.category }}
      </t-tag>
    </div>

    <!-- 施工方经办人 — 纯色蓝 avatar -->
    <div class="card-section contractor-section">
      <span class="section-label">施工方经办人</span>
      <div class="contractor-row">
        <t-avatar size="small" :style="{ background: 'var(--color-brand-500)' }">
          {{ getInitials(item.contractor.name) }}
        </t-avatar>
        <span class="contractor-name">{{ item.contractor.name }}</span>
      </div>
    </div>

    <!-- 金额区块 — 清晰网格 -->
    <div class="card-section amount-section">
      <span class="section-label">造价金额（元）</span>
      <div class="amount-grid">
        <div class="amount-item">
          <span class="amount-label">合同金额</span>
          <span class="amount-value">{{ formatAmount(item.amount.contractAmount) }}</span>
        </div>
        <div class="amount-item amount-item--bold">
          <span class="amount-label">送审金额</span>
          <span class="amount-value">{{ formatAmount(item.amount.submittedAmount) }}</span>
        </div>
        <div class="amount-item">
          <span class="amount-label">一审审定</span>
          <span class="amount-value">{{ formatAmount(item.amount.firstAuditAmount) }}</span>
        </div>
        <div class="amount-item">
          <span class="amount-label">二审审定</span>
          <span class="amount-value">{{ formatAmount(item.amount.secondAuditAmount) }}</span>
        </div>
        <div v-if="item.amount.auditDifference > 0" class="amount-item amount-item--negative">
          <span class="amount-label">审减差额</span>
          <span class="amount-value">-{{ formatAmount(item.amount.auditDifference) }}</span>
        </div>
        <div class="amount-item amount-item--bold">
          <span class="amount-label">定案应付</span>
          <span class="amount-value">{{ formatAmount(item.amount.finalPayable) }}</span>
        </div>
      </div>
    </div>

    <!-- 双审计主体 — 纯色浅底分区 -->
    <div class="card-section audit-parties">
      <div class="audit-party party-first">
        <span class="party-label">一审 · 事务所</span>
        <span class="party-company truncate">{{ item.firstAudit.companyName }}</span>
        <span class="party-person">{{ item.firstAudit.auditor.name }}</span>
        <t-tooltip :content="item.firstAudit.auditor.phone">
          <span class="party-phone" @click.stop="copyPhone(item.firstAudit.auditor.phone)">
            <t-icon name="call" size="12px" />
            {{ item.firstAudit.auditor.phone }}
          </span>
        </t-tooltip>
      </div>
      <div class="audit-party party-second">
        <span class="party-label">二审 · 业主</span>
        <span class="party-company truncate">{{ item.secondAudit.department }}</span>
        <span class="party-person">{{ item.secondAudit.auditor.name }}</span>
        <t-tooltip :content="item.secondAudit.auditor.phone">
          <span class="party-phone" @click.stop="copyPhone(item.secondAudit.auditor.phone)">
            <t-icon name="call" size="12px" />
            {{ item.secondAudit.auditor.phone }}
          </span>
        </t-tooltip>
      </div>
    </div>

    <!-- 时限管控 -->
    <div class="card-section deadline-section">
      <span class="section-label">时限管控</span>
      <div class="deadline-row">
        <span class="deadline-item">报审 {{ formatDate(item.deadline.submitDate) }}</span>
        <span :class="['deadline-item', { overdue: isOverdue(item.deadline.auditDeadline) }]">
          <t-icon v-if="isOverdue(item.deadline.auditDeadline)" name="error-circle" size="12px" />
          截止 {{ formatDate(item.deadline.auditDeadline) }}
        </span>
      </div>
    </div>

    <!-- 资料状态 -->
    <div class="card-section status-section">
      <t-tag :theme="docStatusTheme" variant="light-outline" size="small">
        {{ item.docStatus }}
      </t-tag>
    </div>

    <!-- 业务备注 -->
    <div v-if="item.remark.dispute || item.remark.coordination" class="card-section remark-section">
      <span class="section-label">业务备注</span>
      <p v-if="item.remark.dispute" class="remark-line remark-line--dispute">
        <strong>争议：</strong>{{ item.remark.dispute }}
      </p>
      <p v-if="item.remark.coordination" class="remark-line">
        <strong>协调：</strong>{{ item.remark.coordination }}
      </p>
    </div>

    <!-- 操作按钮 — 仅已登录且未归档 -->
    <div v-if="authStore.isAuthenticated && !item.isArchived" class="card-section card-actions">
      <t-button size="small" variant="text" theme="primary" @click.stop="handleEdit">
        <template #icon><t-icon name="edit" /></template>
        编辑
      </t-button>
      <t-button size="small" variant="text" theme="default" @click.stop="handleCopyInfo">
        <template #icon><t-icon name="file-copy" /></template>
        复制台账
      </t-button>
    </div>

    <!-- 操作日志 -->
    <div class="card-log">
      <span>{{ item.log.operator }} · {{ operateTypeText }} · {{ formatDate(item.log.updateTime) }}</span>
    </div>
  </t-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import type { CostAuditItem } from '@/types'
import { formatAmount, getInitials } from '@/utils/format'
import { formatDate, isOverdue } from '@/utils/date'
import { MessagePlugin } from 'tdesign-vue-next'

const props = defineProps<{
  item: CostAuditItem
  isReturned?: boolean
}>()

const authStore = useAuthStore()

const emit = defineEmits<{
  edit: [item: CostAuditItem]
}>()

const hasDispute = computed(() => !!props.item.remark.dispute?.trim())

const cardClasses = computed(() => ({
  'is-archived': props.item.isArchived,
  'is-returned': props.isReturned,
  'is-disputed': hasDispute.value,
  'is-doc-returned': props.item.docStatus === '资料退回补件',
  'is-readonly': !authStore.isAuthenticated,
}))

const operateTypeText = computed(() => {
  const map: Record<string, string> = { drag_move: '移动', create: '新建', update: '编辑' }
  return map[props.item.log.operateType] ?? '操作'
})

const priorityTheme = computed(() => {
  const map: Record<string, string> = { S0: 'danger', S1: 'warning', S2: 'primary', S3: 'default' }
  return map[props.item.priority] || 'default'
})

const categoryTheme = computed(() => {
  const map: Record<string, string> = {
    '竣工总结算': 'primary', '分部结算': 'success', '现场签证': 'warning',
    '工程变更': 'danger', '土建造价': 'default', '安装造价': 'default',
    '市政结算': 'default', '分包审核': 'default',
  }
  return map[props.item.category] || 'default'
})

const docStatusTheme = computed(() => {
  const map: Record<string, string> = {
    '资料齐全': 'success', '缺图纸': 'warning',
    '缺变更签证': 'danger', '资料退回补件': 'danger',
  }
  return map[props.item.docStatus] || 'default'
})

function copyPhone(phone: string) {
  navigator.clipboard?.writeText(phone).then(
    () => MessagePlugin.success('号码已复制'),
    () => MessagePlugin.warning('复制失败')
  )
}

function handleEdit() { emit('edit', props.item) }

function handleCopyInfo() {
  const info = [
    `项目: ${props.item.projectName}`,
    `楼栋: ${props.item.sectionBuilding}`,
    `编号: ${props.item.settlementNo}`,
    `分类: ${props.item.category}`,
    `送审金额: ${formatAmount(props.item.amount.submittedAmount)}`,
    `一审: ${props.item.firstAudit.companyName} - ${props.item.firstAudit.auditor.name}`,
    `二审: ${props.item.secondAudit.department} - ${props.item.secondAudit.auditor.name}`,
    `截止: ${formatDate(props.item.deadline.auditDeadline)}`,
  ].join('\n')
  navigator.clipboard?.writeText(info).then(
    () => MessagePlugin.success('台账信息已复制'),
    () => MessagePlugin.warning('复制失败')
  )
}
</script>

<style scoped>
/* 未登录只读：移除拖拽手型 */
.audit-card.is-readonly {
  cursor: default;
}
/* ========== 卡片容器 — 纯色 + 1px 边框 ========== */
.audit-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color) !important;
  cursor: grab;
  position: relative;
  user-select: none;
  margin-bottom: var(--space-3);
}

.audit-card:hover {
  border-color: var(--border-color-strong) !important;
}

.audit-card:active {
  cursor: grabbing;
}

/* ── 归档卡片：灰度化、禁用交互 ── */
.audit-card.is-archived {
  opacity: 0.5;
  filter: grayscale(0.8);
  cursor: not-allowed;
  pointer-events: none;
}

/* ── 资料退回：浅橙底色 ── */
.audit-card.is-doc-returned {
  background: var(--color-warning-bg);
  border-color: var(--color-warning-border) !important;
}

/* ── 退回标记：左边 3px 橙色实线 ── */
.audit-card.is-returned {
  border-left: 3px solid var(--color-warning) !important;
}

/* ── 争议三角标记 ── */
.dispute-marker {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
}

.dispute-triangle {
  width: 0;
  height: 0;
  border-style: solid;
  border-width: 20px 20px 0 0;
  border-color: var(--color-danger) transparent transparent transparent;
}

/* ========== 卡片内容分区 — 统一节奏 ========== */
.card-section {
  padding: var(--space-2) var(--space-3);
}

.card-section + .card-section {
  border-top: 1px solid var(--border-color);
}

.section-label {
  display: block;
  font-size: 10px;
  color: var(--text-tertiary);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 4px;
}

/* ── 头部 ── */
.card-header {
  padding: var(--space-3);
}

.project-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: 4px;
}

.project-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.project-meta {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.meta-sep {
  margin: 0 4px;
  color: var(--border-color-strong);
}

.category-tag {
  font-weight: 500;
}

/* ── 经办人 ── */
.contractor-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.contractor-name {
  font-size: var(--text-sm);
  color: var(--color-brand-600);
  font-weight: 500;
}

/* ── 金额网格 ── */
.amount-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px var(--space-2);
  margin-top: 2px;
}

.amount-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1px 0;
}

.amount-item--bold .amount-value {
  font-weight: 700;
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.amount-item--negative .amount-value {
  color: var(--color-danger);
  font-weight: 600;
}

.amount-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.amount-value {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* ── 双审计 ── */
.audit-parties {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.audit-party {
  padding: var(--space-2);
  border: 1px solid var(--border-color);
  font-size: var(--text-xs);
  min-width: 0;
}

.party-first {
  background: var(--color-brand-50);
}

.party-second {
  background: var(--color-gray-50);
}

.party-label {
  font-size: 10px;
  color: var(--text-tertiary);
  display: block;
  margin-bottom: 2px;
}

.party-company {
  font-weight: 600;
  color: var(--text-primary);
  display: block;
  line-height: 1.4;
}

.party-person {
  color: var(--text-secondary);
  display: block;
  line-height: 1.4;
}

.party-phone {
  color: var(--color-brand-500);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-top: 2px;
  transition: color var(--duration-fast);
}

.party-phone:hover {
  color: var(--color-brand-700);
  text-decoration: underline;
}

/* ── 时限 ── */
.deadline-row {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-top: 2px;
}

.deadline-item.overdue {
  color: var(--color-danger);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 3px;
}

/* ── 状态 ── */
.status-section {
  padding-top: var(--space-2);
  padding-bottom: var(--space-2);
}

/* ── 备注 ── */
.remark-line {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin: 2px 0 0;
  line-height: 1.5;
}

.remark-line--dispute {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  padding: 3px 6px;
  border-left: 2px solid var(--color-danger);
}

/* ── 操作 ── */
.card-actions {
  display: flex;
  gap: 2px;
}

/* ── 日志 ── */
.card-log {
  padding: 0 var(--space-3) var(--space-2);
  font-size: 10px;
  color: var(--text-tertiary);
}

/* ========== 拖拽状态 ========== */
:deep(.kanban-ghost) {
  opacity: 0.3;
  background: var(--color-brand-100);
  border: 2px dashed var(--color-brand-500);
}

:deep(.kanban-chosen) {
  outline: 2px solid var(--color-brand-500);
}

:deep(.kanban-drag) {
  opacity: 0.85;
}
</style>
