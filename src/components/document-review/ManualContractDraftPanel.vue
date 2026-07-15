<template>
  <section class="manual-panel">
    <div class="manual-panel__notice">
      <strong>{{ sourceReady ? '已关联合同原件' : '未上传合同只能保存草稿' }}</strong>
      <span>{{ sourceReady ? '填写后进入统一复核工作台，仍需逐项核对原文。' : '草稿不会生成项目编号、生命周期状态或正式项目记录。后续补充合同后再进入复核。' }}</span>
    </div>

    <label v-if="!sourceReady" class="compact-upload">
      <input type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp" @change="pickFile" />
      <strong>{{ fileName || '可选：上传合同扫描件' }}</strong>
      <small>上传后可直接进入人工复核；暂时没有文件也可以保存草稿</small>
    </label>

    <div class="manual-grid">
      <label><span>项目名称</span><AInput :model-value="text('project.name')" placeholder="按合同填写" @update:model-value="set('project.name', $event)" /></label>
      <label><span>建设单位</span><AInput :model-value="text('party.owner')" placeholder="按合同填写" @update:model-value="set('party.owner', $event)" /></label>
      <label><span>施工单位</span><AInput :model-value="text('party.contractor')" placeholder="按合同填写" @update:model-value="set('party.contractor', $event)" /></label>
      <label><span>项目经理</span><AInput :model-value="text('project.manager')" placeholder="合同未明确可留空" @update:model-value="set('project.manager', $event)" /></label>
      <label><span>合同金额</span><AInput :model-value="text('contract.amount')" placeholder="如：1000000 元" @update:model-value="set('contract.amount', $event)" /></label>
      <label><span>合同签订日期</span><AInput :model-value="text('contract.signed_date')" placeholder="YYYY-MM-DD" @update:model-value="set('contract.signed_date', $event)" /></label>
      <label class="manual-grid__wide"><span>付款条款</span><ATextarea :model-value="text('contract.payment_terms')" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="按合同原文填写；暂不清楚可留空" @update:model-value="set('contract.payment_terms', $event)" /></label>
    </div>

    <p v-if="notice" class="manual-panel__result">{{ notice }}</p>
    <footer>
      <AButton variant="outline" :disabled="busy" @click="$emit('back')">返回选择</AButton>
      <div>
        <AButton variant="outline" :loading="busy && action === 'draft'" :disabled="busy" @click="$emit('save-draft')">保存草稿</AButton>
        <AButton v-if="sourceReady || fileName" theme="primary" :loading="busy && action === 'review'" :disabled="busy" @click="$emit('start-review')">进入人工复核</AButton>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import type { ContractDraftValue, ContractDraftValues } from '@/types/documentReview'

const props = defineProps<{
  values: ContractDraftValues
  fileName: string
  sourceReady: boolean
  busy: boolean
  action: 'draft' | 'review' | ''
  notice: string
}>()

const emit = defineEmits<{
  file: [file: File | null]
  back: []
  'save-draft': []
  'start-review': []
  'update-field': [key: string, value: string]
}>()

function text(key: string) {
  const value = props.values[key]
  return Array.isArray(value) ? value.join('\n') : String(value ?? '')
}

function set(key: string, value: ContractDraftValue) {
  emit('update-field', key, String(value ?? ''))
}

function pickFile(event: Event) {
  emit('file', (event.target as HTMLInputElement).files?.[0] || null)
}
</script>

<style scoped>
.manual-panel { width: min(900px, 100%); margin: 0 auto; display: grid; gap: 18px; }
.manual-panel__notice { display: grid; gap: 4px; padding: 14px 16px; border: 1px solid var(--border-color); border-radius: var(--radius-lg, 8px); background: rgba(247,249,253,.9); }
.manual-panel__notice span, .compact-upload small { color: var(--text-secondary); }
.compact-upload { display: grid; gap: 5px; padding: 14px 16px; border: 1px dashed #b8c6dc; border-radius: var(--radius-lg, 8px); background: rgba(248,250,253,.9); cursor: pointer; }
.compact-upload input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.manual-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; }
.manual-grid label { display: grid; gap: 7px; color: var(--text-secondary); font-size: 13px; }
.manual-grid__wide { grid-column: 1 / -1; }
.manual-panel__result { margin: 0; padding: 10px 12px; border-radius: var(--radius-lg, 8px); color: #24623c; background: #eef9f2; }
footer, footer > div { display: flex; justify-content: space-between; gap: 10px; }
@media (max-width: 760px) { .manual-grid { grid-template-columns: 1fr; } .manual-grid__wide { grid-column: auto; } }
</style>
