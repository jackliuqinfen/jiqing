<template>
  <div class="filter-bar">
    <div class="filter-row">
      <!-- 搜索框 -->
      <t-input
        v-model="localKeyword"
        placeholder="搜索项目名/楼栋/结算编号..."
        clearable
        size="medium"
        class="search-box"
        @change="onSearchChange"
      >
        <template #prefix-icon><t-icon name="search" /></template>
      </t-input>

      <div class="filter-divider" />

      <!-- 筛选下拉 -->
      <div class="filter-selects">
        <t-select
          v-model="localFilters.contractor"
          placeholder="经办人"
          clearable filterable
          size="medium"
          class="select-compact"
          :options="contractorOpts"
          @change="onFilterChange"
        />
        <t-select
          v-model="localFilters.priority"
          placeholder="紧急等级"
          clearable
          size="medium"
          class="select-xs"
          :options="priorityOpts"
          @change="onFilterChange"
        />
        <t-select
          v-model="localFilters.category"
          placeholder="工程分类"
          clearable filterable
          size="medium"
          class="select-compact"
          :options="categoryOpts"
          @change="onFilterChange"
        />
        <t-select
          v-model="localFilters.auditUnit"
          placeholder="审计单位"
          clearable filterable
          size="medium"
          class="select-compact"
          :options="auditUnitOpts"
          @change="onFilterChange"
        />
        <t-select
          v-model="localFilters.docStatus"
          placeholder="资料状态"
          clearable
          size="medium"
          class="select-xs"
          :options="docStatusOpts"
          @change="onFilterChange"
        />
      </div>

      <div class="filter-divider" />

      <!-- 快捷操作 -->
      <div class="filter-actions">
        <t-button
          :variant="store.filters.onlyOverdue ? 'base' : 'outline'"
          :theme="store.filters.onlyOverdue ? 'danger' : 'default'"
          size="small"
          @click="toggleOverdue"
        >
          <template #icon><t-icon name="error-circle" /></template>
          超期
        </t-button>
        <t-button
          :variant="store.filters.onlyDisputed ? 'base' : 'outline'"
          :theme="store.filters.onlyDisputed ? 'warning' : 'default'"
          size="small"
          @click="toggleDisputed"
        >
          <template #icon><t-icon name="flag" /></template>
          争议
        </t-button>
        <t-button variant="outline" size="small" @click="handleReset">
          <template #icon><t-icon name="refresh" /></template>
          重置
        </t-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useKanbanStore } from '@/store/kanban'
import { debounce } from '@/utils/debounce'
import type { PriorityLevel, ProjectCategory, DocStatus } from '@/types'

const store = useKanbanStore()

const localKeyword = ref(store.filters.keyword)
const localFilters = ref({
  contractor: store.filters.contractor,
  priority: store.filters.priority as PriorityLevel | '',
  category: store.filters.category as ProjectCategory | '',
  auditUnit: store.filters.auditUnit,
  docStatus: store.filters.docStatus as DocStatus | '',
})

const debouncedSearch = debounce((value: string) => {
  store.filters.keyword = value
}, 300)

function onSearchChange(value: string) { debouncedSearch(value) }
function onFilterChange() { Object.assign(store.filters, localFilters.value) }
function toggleOverdue() { store.filters.onlyOverdue = !store.filters.onlyOverdue }
function toggleDisputed() { store.filters.onlyDisputed = !store.filters.onlyDisputed }

function handleReset() {
  store.resetFilters()
  localKeyword.value = ''
  localFilters.value = { contractor: '', priority: '', category: '', auditUnit: '', docStatus: '' }
}

const priorityOpts = [
  { label: 'S0 特急', value: 'S0' }, { label: 'S1 高', value: 'S1' },
  { label: 'S2 中', value: 'S2' },  { label: 'S3 低', value: 'S3' },
]
const categoryOpts = [
  { label: '竣工总结算', value: '竣工总结算' }, { label: '分部结算', value: '分部结算' },
  { label: '现场签证', value: '现场签证' },     { label: '工程变更', value: '工程变更' },
  { label: '土建造价', value: '土建造价' },     { label: '安装造价', value: '安装造价' },
  { label: '市政结算', value: '市政结算' },     { label: '分包审核', value: '分包审核' },
]
const docStatusOpts = [
  { label: '资料齐全', value: '资料齐全' },     { label: '缺图纸', value: '缺图纸' },
  { label: '缺变更签证', value: '缺变更签证' }, { label: '资料退回补件', value: '资料退回补件' },
]
const contractorOpts = computed(() => store.contractorOptions.map(n => ({ label: n, value: n })))
const auditUnitOpts = computed(() => store.auditUnitOptions.map(u => ({ label: u, value: u })))
</script>

<style scoped>
.filter-bar {
  padding: var(--space-2) var(--space-6);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color-strong);
  flex-shrink: 0;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: nowrap;
}

.filter-divider {
  width: 1px;
  height: 28px;
  background: var(--border-color-strong);
  flex-shrink: 0;
}

.search-box { width: 260px; flex-shrink: 0; }

.filter-selects {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.select-compact { width: 140px; flex-shrink: 0; }
.select-xs { width: 110px; flex-shrink: 0; }

.filter-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

@media (max-width: 1400px) {
  .filter-row { flex-wrap: wrap; }
  .filter-selects { flex-wrap: wrap; }
  .select-compact { width: 124px; }
  .search-box { width: 220px; }
}

@media (max-width: 900px) {
  .filter-bar { padding: var(--space-2) var(--space-4); }
  .filter-divider { display: none; }
  .filter-row { flex-wrap: wrap; }
}
</style>
