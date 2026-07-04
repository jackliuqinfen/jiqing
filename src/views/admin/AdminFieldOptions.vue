<template>
  <div class="admin-page">
    <PageHeader title="业务选项配置" description="维护项目状态、优先级、审计阶段、资料状态等业务下拉选项。">
      <template #meta>
        <ATag color="arcoblue">共 {{ rows.length }} 个选项</ATag>
        <ATag v-if="activeGroup || keyword" color="gray">已应用筛选</ATag>
      </template>
      <template #actions>
        <AButton type="primary" @click="openCreate">
          <template #icon><AIcon name="add" /></template>
          新增选项
        </AButton>
      </template>
    </PageHeader>

    <section class="admin-toolbar">
      <ASelect
        v-model="activeGroup"
        allow-clear
        placeholder="选项组"
        :style="{ width: '220px' }"
        :options="groupOptions"
        @change="load"
      />
      <AInput v-model="keyword" allow-clear placeholder="搜索选项名称、业务值或适用字段" :style="{ width: '320px' }">
        <template #prefix><AIcon name="search" /></template>
      </AInput>
      <AButton type="outline" @click="clearFilters">清除筛选</AButton>
    </section>

    <StatePanel
      v-if="loading"
      state="loading"
      title="正在读取业务选项"
      description="请稍候，系统正在整理当前可选项。"
    />

    <StatePanel
      v-else-if="filteredRows.length === 0"
      state="empty"
      title="没有找到选项"
      description="可以调整筛选条件，或新增一个业务选项。"
    >
      <template #actions>
        <AButton v-if="activeGroup || keyword" type="outline" @click="clearFilters">清除筛选</AButton>
        <AButton type="primary" @click="openCreate">新增选项</AButton>
      </template>
    </StatePanel>

    <section v-else class="admin-table-card">
      <ATable :data="filteredRows" :columns="tableColumns" :loading="loading" bordered hover>
        <template #group="{ row }">
          <div class="option-cell">
            <strong>{{ groupLabel(row.groupKey) }}</strong>
            <span>{{ row.groupKey || '未设置选项组' }}</span>
          </div>
        </template>
        <template #option="{ row }">
          <div class="option-cell">
            <strong>{{ row.optionLabel }}</strong>
            <span>{{ row.optionValue || '未设置业务值' }}</span>
          </div>
        </template>
        <template #field="{ row }">
          <span class="muted-text">{{ row.fieldKey || '未指定适用字段' }}</span>
        </template>
        <template #color="{ row }">
          <span class="color-cell">
            <i class="color-chip" :style="{ background: row.color || '#D1D5DB' }"></i>
            {{ row.color || '未设置' }}
          </span>
        </template>
        <template #enabled="{ row }">
          <ATag :color="row.enabled ? 'green' : 'gray'">{{ row.enabled ? '正常使用' : '已停用' }}</ATag>
        </template>
        <template #operation="{ row }">
          <AButton type="text" size="small" @click="openEdit(row)">编辑</AButton>
        </template>
      </ATable>
    </section>

    <AModal
      v-model:visible="dialog.visible"
      :title="dialog.mode === 'create' ? '新增业务选项' : '编辑业务选项'"
      :ok-text="dialog.mode === 'create' ? '保存选项' : '保存修改'"
      cancel-text="取消"
      :ok-loading="saving"
      :mask-closable="false"
      width="620px"
      @before-ok="save"
    >
      <AForm :model="form" layout="vertical" class="option-form">
        <AFormItem label="选项组" help="用于把同一类选项归在一起，例如项目状态、审计阶段。">
          <AInput v-model="form.groupKey" placeholder="例如 project_status" />
        </AFormItem>
        <AFormItem label="适用字段" help="可选，用于指定该选项适用于哪个业务字段。">
          <AInput v-model="form.fieldKey" placeholder="默认与选项组一致" />
        </AFormItem>
        <AFormItem label="选项名称">
          <AInput v-model="form.optionLabel" placeholder="例如 进行中" />
        </AFormItem>
        <AFormItem label="业务值" help="高级配置：用于稳定保存该选项，保存后不建议频繁修改。">
          <AInput v-model="form.optionValue" placeholder="例如 in_progress" />
        </AFormItem>
        <AFormItem label="标签颜色">
          <AInput v-model="form.color" placeholder="#165DFF 或 green" />
        </AFormItem>
        <AFormItem label="排序">
          <AInputNumber v-model="form.sortOrder" :min="0" :precision="0" />
        </AFormItem>
        <AFormItem label="状态" class="option-form__span">
          <ASwitch v-model="form.enabled" />
          <span class="switch-help">{{ form.enabled ? '正常使用，用户可以选择该选项' : '已停用，用户暂时不可选择该选项' }}</span>
        </AFormItem>
      </AForm>
    </AModal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { MessagePlugin } from '@/ui/message'
import { fetchFieldOptions, saveFieldOption } from '@/api/audit'
import type { AuditFieldOption } from '@/types/audit'
import { optionGroupLabel } from '@/utils/businessDictionaries'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'

const rows = ref<AuditFieldOption[]>([])
const loading = ref(false)
const saving = ref(false)
const activeGroup = ref('')
const keyword = ref('')
const dialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit' })
const form = reactive<Partial<AuditFieldOption>>({})

const tableColumns = [
  { colKey: 'group', title: '选项组', width: 190 },
  { colKey: 'option', title: '选项', width: 220 },
  { colKey: 'field', title: '适用字段', width: 160 },
  { colKey: 'color', title: '颜色', width: 150 },
  { colKey: 'sortOrder', title: '排序', width: 90 },
  { colKey: 'enabled', title: '状态', width: 110 },
  { colKey: 'operation', title: '操作', width: 90, fixed: 'right' as const },
]

const groupOptions = computed(() => {
  const groups = Array.from(new Set(rows.value.map((row) => row.groupKey).filter(Boolean))).sort()
  return groups.map((group) => ({ label: groupLabel(group), value: group }))
})

const filteredRows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    const matchKeyword = !kw || [row.groupKey, row.fieldKey, row.optionLabel, row.optionValue]
      .some((value) => String(value || '').toLowerCase().includes(kw))
    return matchKeyword
  })
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    rows.value = await fetchFieldOptions(activeGroup.value || undefined)
  } catch {
    MessagePlugin.error('业务选项加载失败，请稍后重试或联系管理员。')
  } finally {
    loading.value = false
  }
}

function defaultForm(): Partial<AuditFieldOption> {
  return {
    id: '',
    groupKey: activeGroup.value || '',
    fieldKey: activeGroup.value || '',
    optionLabel: '',
    optionValue: '',
    color: '',
    sortOrder: 100,
    enabled: true,
  }
}

function openCreate() {
  Object.assign(form, defaultForm())
  dialog.mode = 'create'
  dialog.visible = true
}

function openEdit(item: AuditFieldOption) {
  Object.assign(form, defaultForm(), item)
  dialog.mode = 'edit'
  dialog.visible = true
}

function clearFilters() {
  activeGroup.value = ''
  keyword.value = ''
  load()
}

function groupLabel(value?: string) {
  return optionGroupLabel(value)
}

async function save() {
  if (!form.groupKey || !form.optionLabel || !form.optionValue) {
    MessagePlugin.warning('请填写选项组、选项名称和业务值，便于用户稳定选择。')
    return false
  }
  saving.value = true
  try {
    await saveFieldOption({ ...form, fieldKey: form.fieldKey || form.groupKey })
    MessagePlugin.success('业务选项已保存')
    dialog.visible = false
    await load()
    return true
  } catch {
    MessagePlugin.error('业务选项保存失败，请稍后重试或联系管理员。')
    return false
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-page { max-width: 1180px; }
.admin-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}
.admin-table-card {
  overflow: hidden;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}
.option-cell { display: grid; gap: 2px; min-width: 0; }
.option-cell strong { color: var(--text-primary); }
.option-cell span,
.muted-text { color: var(--text-secondary); font-size: var(--text-xs); }
.color-cell { display: inline-flex; align-items: center; gap: 8px; }
.color-chip {
  width: 14px;
  height: 14px;
  display: inline-block;
  border: 1px solid var(--border-color);
  border-radius: 3px;
}
.option-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2) var(--space-4);
}
.option-form__span { grid-column: 1 / -1; }
.switch-help { margin-left: var(--space-2); color: var(--text-secondary); font-size: var(--text-sm); }
@media (max-width: 760px) {
  .option-form { grid-template-columns: 1fr; }
}
</style>
