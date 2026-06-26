<template>
  <div
    :data-stage="column.id"
    :data-locked="column.locked ? 'true' : 'false'"
    class="kanban-column"
  >
    <!-- 列头部 — 纯色圆点 + 纯文字 -->
    <div class="column-header">
      <div class="column-title-row">
        <span class="column-dot" :style="{ background: headerColor }" />
        <span class="column-title">{{ column.title }}</span>
        <t-badge :count="cards.length" :offset="[0, 0]" size="small" />
      </div>
      <div v-if="column.locked" class="column-locked-hint">
        <t-icon name="lock-on" size="11px" />
        <span>已锁定</span>
      </div>
    </div>

    <!-- 列体 -->
    <div :id="`kanban-body-${column.id}`" class="kanban-column-body">
      <div v-if="cards.length === 0" class="column-empty">
        <t-icon name="inbox" size="28px" />
        <span>暂无项目</span>
      </div>

      <AuditCard
        v-for="card in cards"
        :key="card.id"
        :item="card"
        :is-returned="isReturnedCard(card)"
        :data-card-id="card.id"
        :data-stage="card.stage"
        class="kanban-card-handle"
        @edit="handleEdit"
      />
    </div>

    <!-- 列底部 -->
    <div class="column-footer">
      <span>{{ cards.length }} 个项目</span>
      <span v-if="totalAmount > 0" class="footer-amount">{{ formatCNY(totalAmount) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { KanbanColumnDef, CostAuditItem, KanbanStage } from '@/types'
import { formatCNY } from '@/utils/format'
import AuditCard from './AuditCard.vue'

const props = defineProps<{
  column: KanbanColumnDef
  cards: CostAuditItem[]
}>()

const emit = defineEmits<{ edit: [item: CostAuditItem] }>()

const headerColor = computed(() => {
  const map: Record<KanbanStage, string> = {
    submitted: 'var(--color-stage-submitted)',
    first_audit: 'var(--color-stage-first-audit)',
    second_audit: 'var(--color-stage-second-audit)',
    conclusion: 'var(--color-stage-conclusion)',
    archived: 'var(--color-stage-archived)',
  }
  return map[props.column.id] || 'var(--color-brand-500)'
})

const totalAmount = computed(() =>
  props.cards.reduce((sum, c) => sum + c.amount.submittedAmount, 0)
)

function isReturnedCard(card: CostAuditItem) {
  return card.docStatus === '资料退回补件'
}

function handleEdit(item: CostAuditItem) { emit('edit', item) }
</script>

<style scoped>
.kanban-column {
  min-width: 300px;
  max-width: 330px;
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-muted);
  border: 1px solid var(--border-color-strong);
  padding: var(--space-3);
  height: fit-content;
  max-height: calc(100vh - 240px);
}

/* ── 列头 — 去除彩色顶边，只用圆点标识 ── */
.column-header {
  padding: var(--space-2) var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-color);
  margin-bottom: var(--space-2);
}

.column-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.column-dot {
  width: 10px; height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.column-title {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-primary);
  flex: 1;
}

.column-locked-hint {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 4px;
  margin-left: 18px;
}

/* ── 列体 ── */
.kanban-column-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 2px 2px var(--space-2);
  min-height: 120px;
  max-height: calc(100vh - 340px);
}

.kanban-column-body::-webkit-scrollbar { width: 4px; }
.kanban-column-body::-webkit-scrollbar-thumb {
  background: var(--color-gray-200);
  border-radius: 2px;
}

/* ── 空状态 ── */
.column-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-4);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  margin: 2px;
}

.column-empty :deep(.t-icon) { color: var(--color-gray-200); }

/* ── 列底部 ── */
.column-footer {
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.footer-amount {
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1200px) {
  .kanban-column { min-width: 280px; max-width: 300px; }
}
</style>
