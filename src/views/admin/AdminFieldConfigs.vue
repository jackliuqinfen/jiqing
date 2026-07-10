<template>
  <div class="admin-page">
    <PageHeader title="审计字段配置" description="维护审计看板、审计详情和编辑表单中的字段名称、展示位置和表格列宽。">
      <template #meta>
        <ATag color="arcoblue">共 {{ rows.length }} 个字段</ATag>
        <ATag v-if="keyword || moduleFilter" color="gray">已应用筛选</ATag>
      </template>
      <template #actions>
        <AButton type="primary" @click="openCreate">
          <template #icon><AIcon name="add" /></template>
          新增字段
        </AButton>
      </template>
    </PageHeader>

    <section class="admin-toolbar">
      <AInput v-model="keyword" allow-clear placeholder="搜索字段名称、字段标识或关联数据项" :style="{ width: '320px' }">
        <template #prefix><AIcon name="search" /></template>
      </AInput>
      <ASelect v-model="moduleFilter" allow-clear placeholder="所属模块" :style="{ width: '180px' }" :options="moduleOptions" />
      <AButton type="outline" @click="clearFilters">清除筛选</AButton>
    </section>

    <StatePanel
      v-if="loading"
      state="loading"
      title="正在读取字段配置"
      description="请稍候，系统正在整理当前看板字段。"
    />

    <StatePanel
      v-else-if="filteredRows.length === 0"
      state="empty"
      title="没有找到字段"
      description="可以调整筛选条件，或新增一个字段用于看板展示。"
    >
      <template #actions>
        <AButton v-if="keyword || moduleFilter" type="outline" @click="clearFilters">清除筛选</AButton>
        <AButton type="primary" @click="openCreate">新增字段</AButton>
      </template>
    </StatePanel>

    <section v-else class="admin-table-card">
      <ATable :data="filteredRows" :columns="tableColumns" :loading="loading" bordered hover>
        <template #field="{ row }">
          <div class="field-cell">
            <strong>{{ row.fieldLabel }}</strong>
            <span>{{ row.fieldKey || '未设置字段标识' }}</span>
          </div>
        </template>
        <template #module="{ row }">
          <ATag color="arcoblue">{{ moduleLabel(row.module) }}</ATag>
        </template>
        <template #stage="{ row }">
          <span>{{ stageLabel(row.stageKey) }}</span>
        </template>
        <template #scene="{ row }">
          <span>{{ sceneText(row) || '未选择展示位置' }}</span>
        </template>
        <template #binding="{ row }">
          <span class="muted-text">{{ row.bindField || '未关联数据项' }}</span>
        </template>
        <template #enabled="{ row }">
          <ATag :color="row.enabled ? 'green' : 'gray'">{{ row.enabled ? '启用中' : '已停用' }}</ATag>
        </template>
        <template #operation="{ row }">
          <AButton type="text" size="small" @click="openEdit(row)">编辑</AButton>
        </template>
      </ATable>
    </section>

    <AModal
      v-model:visible="dialog.visible"
      :title="dialog.mode === 'create' ? '新增字段' : '编辑字段'"
      :ok-text="dialog.mode === 'create' ? '保存字段' : '保存修改'"
      cancel-text="取消"
      :ok-loading="saving"
      :mask-closable="false"
      width="760px"
      @before-ok="save"
    >
      <AForm :model="form" layout="vertical" class="field-form">
        <AFormItem label="字段标识" help="高级配置：用于稳定识别同一个字段，保存后不建议频繁修改。">
          <AInput v-model="form.fieldKey" placeholder="例如 songshen_amount" />
        </AFormItem>
        <AFormItem label="字段名称">
          <AInput v-model="form.fieldLabel" placeholder="例如 送审金额" />
        </AFormItem>
        <AFormItem label="字段类型">
          <ASelect v-model="form.fieldType" :options="fieldTypeOptions" />
        </AFormItem>
        <AFormItem label="所属模块">
          <ASelect v-model="form.module" :options="moduleOptions" />
        </AFormItem>
        <AFormItem label="所属阶段">
          <ASelect v-model="form.stageKey" allow-clear :options="stageOptions" placeholder="不限定阶段" />
        </AFormItem>
        <AFormItem label="选项组">
          <AInput v-model="form.optionGroup" placeholder="下拉字段需要填写，例如 priority" />
        </AFormItem>
        <AFormItem label="关联数据项" help="高级配置：用于指定字段对应的项目或审计资料数据。">
          <AInput v-model="form.bindField" placeholder="例如送审金额对应的数据项" />
        </AFormItem>
        <AFormItem label="输入提示">
          <AInput v-model="form.placeholder" placeholder="填写时展示给用户的提示" />
        </AFormItem>
        <AFormItem label="默认值">
          <AInput v-model="form.defaultValue" placeholder="可选" />
        </AFormItem>
        <AFormItem label="排序">
          <AInputNumber v-model="form.sortOrder" :min="0" :precision="0" />
        </AFormItem>
        <AFormItem label="表格列宽">
          <AInputNumber v-model="form.tableWidth" :min="96" :precision="0" />
        </AFormItem>
        <AFormItem label="展示位置" class="field-form__span">
          <div class="check-grid">
            <ACheckbox v-model="form.visibleInCard">看板卡片</ACheckbox>
            <ACheckbox v-model="form.visibleInTable">表格列</ACheckbox>
            <ACheckbox v-model="form.visibleInDetail">审计详情展示</ACheckbox>
            <ACheckbox v-model="form.visibleInForm">审计详情编辑表单</ACheckbox>
            <ACheckbox v-model="form.visibleInGantt">甘特视图</ACheckbox>
            <ACheckbox v-model="form.required">必填项</ACheckbox>
            <ACheckbox v-model="form.enabled">启用字段</ACheckbox>
          </div>
        </AFormItem>
      </AForm>
    </AModal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { MessagePlugin } from '@/ui/message'
import { fetchFieldConfigs, saveFieldConfig } from '@/api/audit'
import type { AuditFieldConfig } from '@/types/audit'
import { auditStageOptions, businessLabel } from '@/utils/businessDictionaries'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'

const rows = ref<AuditFieldConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const keyword = ref('')
const moduleFilter = ref('')
const dialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit' })
const form = reactive<Partial<AuditFieldConfig>>({})

const tableColumns = [
  { colKey: 'field', title: '字段', width: 220 },
  { colKey: 'fieldType', title: '类型', width: 110 },
  { colKey: 'module', title: '所属模块', width: 120 },
  { colKey: 'stage', title: '所属阶段', width: 130 },
  { colKey: 'scene', title: '展示位置', width: 180 },
  { colKey: 'binding', title: '关联数据项', ellipsis: true },
  { colKey: 'sortOrder', title: '排序', width: 80 },
  { colKey: 'enabled', title: '状态', width: 90 },
  { colKey: 'operation', title: '操作', width: 90, fixed: 'right' as const },
]

const moduleOptions = [
  { label: '审计项目字段', value: 'project' },
  { label: '审计阶段字段', value: 'stage' },
]

const stageOptions = auditStageOptions.map(({ label, value }) => ({ label, value }))

const fieldTypeOptions = [
  { label: '文本', value: 'text' },
  { label: '多行文本', value: 'textarea' },
  { label: '数字', value: 'number' },
  { label: '日期', value: 'date' },
  { label: '单选', value: 'select' },
  { label: '多选', value: 'multi_select' },
  { label: '人员', value: 'person' },
  { label: '状态', value: 'status' },
  { label: '百分比', value: 'percent' },
  { label: '是否', value: 'boolean' },
]

const filteredRows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    const matchKeyword = !kw || [row.fieldLabel, row.fieldKey, row.bindField].some((value) => String(value || '').toLowerCase().includes(kw))
    const matchModule = !moduleFilter.value || row.module === moduleFilter.value
    return matchKeyword && matchModule
  })
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    rows.value = await fetchFieldConfigs()
  } catch {
    MessagePlugin.error('字段配置加载失败，请稍后重试或联系管理员。')
  } finally {
    loading.value = false
  }
}

function defaultForm(): Partial<AuditFieldConfig> {
  return {
    id: '',
    entityType: 'project',
    fieldKey: '',
    fieldLabel: '',
    fieldType: 'text',
    module: 'project',
    displayScene: '',
    stageKey: '',
    optionGroup: '',
    bindField: '',
    placeholder: '',
    defaultValue: '',
    required: false,
    visibleInCard: true,
    visibleInTable: true,
    visibleInDetail: true,
    visibleInForm: true,
    visibleInGantt: false,
    tableWidth: 140,
    sortOrder: 100,
    enabled: true,
  }
}

function openCreate() {
  Object.assign(form, defaultForm())
  dialog.mode = 'create'
  dialog.visible = true
}

function openEdit(item: AuditFieldConfig) {
  Object.assign(form, defaultForm(), item)
  dialog.mode = 'edit'
  dialog.visible = true
}

function clearFilters() {
  keyword.value = ''
  moduleFilter.value = ''
}

function moduleLabel(value?: string) {
  return moduleOptions.find((item) => item.value === value)?.label || '未设置'
}

function stageLabel(value?: string) {
  return businessLabel(auditStageOptions, value, '不限定阶段')
}

function sceneText(item: AuditFieldConfig) {
  return [
    item.visibleInCard ? '看板卡片' : '',
    item.visibleInTable ? '表格列' : '',
    item.visibleInDetail ? '审计详情展示' : '',
    item.visibleInForm ? '审计详情编辑表单' : '',
    item.visibleInGantt ? '甘特' : '',
  ].filter(Boolean).join(' / ')
}

async function save() {
  if (!form.fieldKey || !form.fieldLabel) {
    MessagePlugin.warning('请填写字段标识和字段名称，便于后续在看板中稳定展示。')
    return false
  }
  saving.value = true
  try {
    await saveFieldConfig(form)
    MessagePlugin.success('字段配置已保存')
    dialog.visible = false
    await load()
    return true
  } catch {
    MessagePlugin.error('字段配置保存失败，请稍后重试或联系管理员。')
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
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.field-cell { display: grid; gap: 2px; min-width: 0; }
.field-cell strong { color: var(--text-primary); }
.field-cell span,
.muted-text { color: var(--text-secondary); font-size: var(--text-xs); }
.field-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2) var(--space-4);
}
.field-form__span { grid-column: 1 / -1; }
.check-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}
.check-grid label { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); }
@media (max-width: 760px) {
  .field-form,
  .check-grid { grid-template-columns: 1fr; }
}
</style>
