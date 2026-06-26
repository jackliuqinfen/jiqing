<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h2>字段配置</h2>
        <p>配置项目字段在卡片、表格、详情、表单和甘特视图中的显隐。</p>
      </div>
      <t-button theme="primary" @click="startCreate">新增字段</t-button>
    </div>

    <div class="config-layout">
      <section class="panel">
        <table>
          <thead>
            <tr>
              <th>字段</th>
              <th>类型</th>
              <th>绑定</th>
              <th>视图</th>
              <th>排序</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in rows" :key="item.id">
              <td><strong>{{ item.fieldLabel }}</strong><span>{{ item.fieldKey }}</span></td>
              <td>{{ item.fieldType }}</td>
              <td>{{ item.bindField || '-' }}</td>
              <td>{{ visibleText(item) }}</td>
              <td>{{ item.sortOrder }}</td>
              <td><button class="link-button" @click="startEdit(item)">编辑</button></td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel editor">
        <h3>{{ form.id ? '编辑字段' : '新增字段' }}</h3>
        <label>字段键<input v-model="form.fieldKey" class="native-input" /></label>
        <label>字段名称<input v-model="form.fieldLabel" class="native-input" /></label>
        <label>字段类型
          <select v-model="form.fieldType" class="native-input">
            <option value="text">text</option>
            <option value="textarea">textarea</option>
            <option value="number">number</option>
            <option value="date">date</option>
            <option value="select">select</option>
            <option value="multi_select">multi_select</option>
            <option value="person">person</option>
            <option value="status">status</option>
            <option value="percent">percent</option>
            <option value="boolean">boolean</option>
          </select>
        </label>
        <label>所属模块<input v-model="form.module" class="native-input" placeholder="project / stage" /></label>
        <label>显示场景<input v-model="form.displayScene" class="native-input" placeholder="card,table,detail,form,gantt" /></label>
        <label>所属阶段<input v-model="form.stageKey" class="native-input" placeholder="可选" /></label>
        <label>选项组<input v-model="form.optionGroup" class="native-input" placeholder="select 字段填写" /></label>
        <label>绑定路径<input v-model="form.bindField" class="native-input" placeholder="如 amount.submittedAmount" /></label>
        <label>输入提示<input v-model="form.placeholder" class="native-input" /></label>
        <label>默认值<input v-model="form.defaultValue" class="native-input" /></label>
        <label>排序<input v-model.number="form.sortOrder" type="number" class="native-input" /></label>
        <div class="checks">
          <label><input v-model="form.required" type="checkbox" /> 必填</label>
          <label><input v-model="form.visibleInCard" type="checkbox" /> 卡片</label>
          <label><input v-model="form.visibleInTable" type="checkbox" /> 表格</label>
          <label><input v-model="form.visibleInDetail" type="checkbox" /> 详情</label>
          <label><input v-model="form.visibleInForm" type="checkbox" /> 表单</label>
          <label><input v-model="form.visibleInGantt" type="checkbox" /> 甘特</label>
          <label><input v-model="form.enabled" type="checkbox" /> 启用</label>
        </div>
        <div class="actions">
          <t-button variant="outline" @click="startCreate">清空</t-button>
          <t-button theme="primary" :loading="saving" @click="save">保存</t-button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { fetchFieldConfigs, saveFieldConfig } from '@/api/audit'
import type { AuditFieldConfig } from '@/types/audit'

const rows = ref<AuditFieldConfig[]>([])
const saving = ref(false)
const form = reactive<Partial<AuditFieldConfig>>({})

onMounted(load)

async function load() {
  rows.value = await fetchFieldConfigs()
}

function startCreate() {
  Object.assign(form, {
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
    sortOrder: 100,
    enabled: true,
  })
}

function startEdit(item: AuditFieldConfig) {
  Object.assign(form, item)
}

function visibleText(item: AuditFieldConfig) {
  return [
    item.visibleInCard ? '卡' : '',
    item.visibleInTable ? '表' : '',
    item.visibleInDetail ? '详' : '',
    item.visibleInForm ? '单' : '',
    item.visibleInGantt ? '甘' : '',
  ].filter(Boolean).join(' / ')
}

async function save() {
  if (!form.fieldKey || !form.fieldLabel) {
    MessagePlugin.warning('字段键和字段名称不能为空')
    return
  }
  saving.value = true
  try {
    await saveFieldConfig(form)
    MessagePlugin.success('字段配置已保存')
    await load()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-page { max-width: 1180px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-5); }
.page-header h2 { margin: 0 0 4px; font-size: var(--text-2xl); }
.page-header p { margin: 0; color: var(--text-secondary); }
.config-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--space-4); }
.panel { background: var(--bg-surface); border: 1px solid var(--border-color-strong); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px; border-bottom: 1px solid var(--border-color); text-align: left; font-size: var(--text-sm); }
th { background: var(--bg-muted); color: var(--text-secondary); }
td span { display: block; color: var(--text-tertiary); font-size: var(--text-xs); margin-top: 2px; }
.link-button { border: 0; background: transparent; color: var(--color-brand-500); cursor: pointer; }
.editor { padding: var(--space-4); display: grid; gap: var(--space-3); align-self: start; }
.editor h3 { margin: 0; }
.editor label { display: grid; gap: 5px; font-size: var(--text-sm); color: var(--text-secondary); }
.native-input { border: 1px solid var(--border-color-strong); min-height: 32px; padding: 5px 8px; font: inherit; background: #fff; }
.checks { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.checks label { display: flex; align-items: center; gap: 6px; }
.actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
@media (max-width: 980px) { .config-layout { grid-template-columns: 1fr; } }
</style>
