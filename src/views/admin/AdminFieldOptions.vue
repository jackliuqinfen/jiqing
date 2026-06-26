<template>
  <div class="admin-page">
    <div class="page-header">
      <div>
        <h2>选项库</h2>
        <p>维护分类、优先级、阶段、资料状态、经办人等下拉选项。</p>
      </div>
      <t-button theme="primary" @click="startCreate">新增选项</t-button>
    </div>

    <section class="toolbar">
      <select v-model="activeGroup" class="native-input" @change="load">
        <option value="">全部分组</option>
        <option v-for="group in groups" :key="group" :value="group">{{ group }}</option>
      </select>
    </section>

    <div class="config-layout">
      <section class="panel">
        <table>
          <thead>
            <tr>
              <th>分组</th>
              <th>名称</th>
              <th>值</th>
              <th>颜色</th>
              <th>排序</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in rows" :key="item.id">
              <td>{{ item.groupKey }}</td>
              <td>{{ item.optionLabel }}</td>
              <td>{{ item.optionValue }}</td>
              <td><span class="color-chip" :style="{ background: item.color || '#D1D5DB' }"></span>{{ item.color || '-' }}</td>
              <td>{{ item.sortOrder }}</td>
              <td>{{ item.enabled ? '启用' : '禁用' }}</td>
              <td><button class="link-button" @click="startEdit(item)">编辑</button></td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel editor">
        <h3>{{ form.id ? '编辑选项' : '新增选项' }}</h3>
        <label>分组键<input v-model="form.groupKey" class="native-input" placeholder="category / priority / stage" /></label>
        <label>字段键<input v-model="form.fieldKey" class="native-input" placeholder="默认同分组键" /></label>
        <label>显示名称<input v-model="form.optionLabel" class="native-input" /></label>
        <label>实际值<input v-model="form.optionValue" class="native-input" /></label>
        <label>颜色<input v-model="form.color" class="native-input" placeholder="#3366FF" /></label>
        <label>排序<input v-model.number="form.sortOrder" type="number" class="native-input" /></label>
        <label class="inline"><input v-model="form.enabled" type="checkbox" /> 启用</label>
        <div class="actions">
          <t-button variant="outline" @click="startCreate">清空</t-button>
          <t-button theme="primary" :loading="saving" @click="save">保存</t-button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { fetchFieldOptions, saveFieldOption } from '@/api/audit'
import type { AuditFieldOption } from '@/types/audit'

const rows = ref<AuditFieldOption[]>([])
const activeGroup = ref('')
const saving = ref(false)
const form = reactive<Partial<AuditFieldOption>>({})
const groups = computed(() => Array.from(new Set(rows.value.map((row) => row.groupKey))).sort())

onMounted(load)

async function load() {
  rows.value = await fetchFieldOptions(activeGroup.value || undefined)
}

function startCreate() {
  Object.assign(form, {
    id: '',
    groupKey: activeGroup.value || '',
    fieldKey: activeGroup.value || '',
    optionLabel: '',
    optionValue: '',
    color: '',
    sortOrder: 100,
    enabled: true,
  })
}

function startEdit(item: AuditFieldOption) {
  Object.assign(form, item)
}

async function save() {
  if (!form.groupKey || !form.optionLabel) {
    MessagePlugin.warning('分组键和显示名称不能为空')
    return
  }
  saving.value = true
  try {
    await saveFieldOption(form)
    MessagePlugin.success('选项已保存')
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
.toolbar { margin-bottom: var(--space-3); }
.config-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--space-4); }
.panel { background: var(--bg-surface); border: 1px solid var(--border-color-strong); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px; border-bottom: 1px solid var(--border-color); text-align: left; font-size: var(--text-sm); }
th { background: var(--bg-muted); color: var(--text-secondary); }
.link-button { border: 0; background: transparent; color: var(--color-brand-500); cursor: pointer; }
.color-chip { width: 12px; height: 12px; display: inline-block; margin-right: 6px; border: 1px solid var(--border-color); vertical-align: -1px; }
.editor { padding: var(--space-4); display: grid; gap: var(--space-3); align-self: start; }
.editor h3 { margin: 0; }
.editor label { display: grid; gap: 5px; font-size: var(--text-sm); color: var(--text-secondary); }
.editor .inline { display: flex; align-items: center; gap: 6px; }
.native-input { border: 1px solid var(--border-color-strong); min-height: 32px; padding: 5px 8px; font: inherit; background: #fff; }
.actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
@media (max-width: 980px) { .config-layout { grid-template-columns: 1fr; } }
</style>
