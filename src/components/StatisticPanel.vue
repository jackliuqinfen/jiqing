<template>
  <div class="statistic-panel" role="region" aria-label="全局统计">
    <!-- 数量维度 -->
    <div class="stat-row">
      <div class="stat-item">
        <div class="stat-icon" style="background:var(--color-brand-50); color:var(--color-brand-500)">
          <t-icon name="view-module" size="16px" />
        </div>
        <div class="stat-body">
          <span class="stat-label">总报审</span>
          <span class="stat-value">{{ stats.totalProjects }}</span>
        </div>
      </div>

      <div class="stat-item">
        <div class="stat-icon" style="background:var(--color-warning-bg); color:var(--color-warning)">
          <t-icon name="task" size="16px" />
        </div>
        <div class="stat-body">
          <span class="stat-label">在审</span>
          <span class="stat-value" style="color:var(--color-warning)">{{ stats.inAuditProjects }}</span>
        </div>
      </div>

      <div class="stat-item">
        <div class="stat-icon" style="background:var(--color-success-bg); color:var(--color-success)">
          <t-icon name="check-circle" size="16px" />
        </div>
        <div class="stat-body">
          <span class="stat-label">已办结</span>
          <span class="stat-value" style="color:var(--color-success)">{{ stats.completedProjects }}</span>
        </div>
      </div>

      <div class="stat-item stat-item--danger">
        <div class="stat-icon" style="background:var(--color-danger-bg); color:var(--color-danger)">
          <t-icon name="error-circle" size="16px" />
        </div>
        <div class="stat-body">
          <span class="stat-label">超期督办</span>
          <span class="stat-value" :style="{ color: stats.overdueProjects > 0 ? 'var(--color-danger)' : 'var(--text-primary)' }">
            {{ stats.overdueProjects }}
          </span>
        </div>
      </div>
    </div>

    <div class="stat-divider" />

    <!-- 金额维度 -->
    <div class="stat-row">
      <div class="stat-item stat-item--wide">
        <div class="stat-body">
          <span class="stat-label">总送审金额</span>
          <div class="stat-amount-row">
            <span class="stat-value">{{ formatAmount(stats.totalSubmittedAmount) }}</span>
            <span class="stat-unit">万元</span>
          </div>
        </div>
      </div>

      <div class="stat-item stat-item--wide">
        <div class="stat-body">
          <span class="stat-label">一审审减</span>
          <div class="stat-amount-row">
            <span
              class="stat-value"
              :style="{ color: stats.totalFirstCutAmount > 0 ? 'var(--color-warning)' : 'var(--text-primary)' }"
            >{{ formatAmount(stats.totalFirstCutAmount) }}</span>
            <span class="stat-unit">万元</span>
          </div>
        </div>
      </div>

      <div class="stat-item stat-item--wide">
        <div class="stat-body">
          <span class="stat-label">二审审减</span>
          <div class="stat-amount-row">
            <span
              class="stat-value"
              :style="{ color: stats.totalSecondCutAmount > 0 ? 'var(--color-danger)' : 'var(--text-primary)' }"
            >{{ formatAmount(stats.totalSecondCutAmount) }}</span>
            <span class="stat-unit">万元</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useKanbanStore } from '@/store/kanban'

const store = useKanbanStore()
const stats = computed(() => store.statistics)

function formatAmount(value: number): string {
  return (value / 10000).toFixed(2)
}
</script>

<style scoped>
.statistic-panel {
  display: flex;
  align-items: stretch;
  gap: 0;
  padding: var(--space-2) var(--space-6);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color-strong);
  flex-shrink: 0;
  overflow-x: auto;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.stat-divider {
  width: 1px;
  background: var(--border-color-strong);
  margin: var(--space-2) var(--space-3);
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  min-width: 120px;
}

.stat-item--wide {
  min-width: 140px;
}

.stat-icon {
  width: 30px; height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-body {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 0;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  font-weight: 500;
}

.stat-value {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.stat-amount-row {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
}

.stat-unit {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.stat-item--danger .stat-body {
  position: relative;
}

@media (max-width: 1200px) {
  .statistic-panel { padding: var(--space-2) var(--space-4); }
  .stat-item { min-width: 100px; padding: var(--space-1) var(--space-2); }
  .stat-value { font-size: var(--text-lg); }
}
</style>
