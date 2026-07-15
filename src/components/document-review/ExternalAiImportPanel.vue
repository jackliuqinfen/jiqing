<template>
  <section class="external-panel">
    <div class="external-panel__notice">
      <strong>先保护合同隐私</strong>
      <span>请仅使用公司允许的 AI 工具，并确认合同可以上传到该工具。系统不会主动把合同发送给外部平台。</span>
    </div>

    <div class="external-panel__steps">
      <section>
        <div class="step-title"><span>1</span><strong>准备合同</strong></div>
        <p v-if="sourceReady">系统已保留本次上传的合同，可直接粘贴识别结果。</p>
        <label v-else class="compact-upload">
          <input type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp" @change="pickFile" />
          <strong>{{ fileName || '选择合同扫描件' }}</strong>
          <small>进入复核时用于对照原文，必须上传</small>
        </label>
      </section>

      <section>
        <div class="step-title"><span>2</span><strong>复制提示词</strong></div>
        <div class="prompt-box">
          <pre>{{ prompt }}</pre>
          <AButton size="small" variant="outline" @click="$emit('copy')">{{ copied ? '已复制' : '复制提示词' }}</AButton>
        </div>
      </section>

      <section>
        <div class="step-title"><span>3</span><strong>粘贴完整结果</strong></div>
        <ATextarea
          :model-value="markdown"
          :auto-size="{ minRows: 8, maxRows: 12 }"
          placeholder="请粘贴 AI 返回的完整 Markdown，必须包含一个 json 代码块"
          @update:model-value="$emit('update:markdown', String($event || ''))"
        />
      </section>
    </div>

    <p v-if="errorMessage" class="external-panel__error">{{ errorMessage }}</p>

    <footer>
      <AButton variant="outline" :disabled="busy" @click="$emit('back')">返回选择</AButton>
      <AButton theme="primary" :loading="busy" :disabled="!canSubmit" @click="$emit('submit')">解析并进入人工复核</AButton>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  fileName: string
  sourceReady: boolean
  markdown: string
  prompt: string
  copied: boolean
  busy: boolean
  errorMessage: string
}>()

const emit = defineEmits<{
  file: [file: File | null]
  copy: []
  back: []
  submit: []
  'update:markdown': [value: string]
}>()

const canSubmit = computed(() => (props.sourceReady || !!props.fileName) && props.markdown.trim().length > 0 && !props.busy)

function pickFile(event: Event) {
  emit('file', (event.target as HTMLInputElement).files?.[0] || null)
}
</script>

<style scoped>
.external-panel { width: min(900px, 100%); margin: 0 auto; display: grid; gap: 18px; }
.external-panel__notice { display: grid; gap: 4px; padding: 14px 16px; border: 1px solid #f2d59b; border-radius: var(--radius-lg, 8px); background: #fffaf0; }
.external-panel__notice span, .external-panel__steps p, .compact-upload small { color: var(--text-secondary); }
.external-panel__steps { display: grid; gap: 18px; }
.external-panel__steps > section { display: grid; gap: 10px; }
.step-title { display: flex; align-items: center; gap: 8px; }
.step-title span { width: 24px; height: 24px; display: grid; place-content: center; border-radius: 50%; color: #fff; background: var(--primary-color); font-size: 12px; font-weight: 700; }
.external-panel__steps p { margin: 0; }
.compact-upload { display: grid; gap: 5px; padding: 14px 16px; border: 1px dashed #b8c6dc; border-radius: var(--radius-lg, 8px); background: rgba(248,250,253,.9); cursor: pointer; }
.compact-upload input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.prompt-box { position: relative; min-height: 150px; padding: 15px; border: 1px solid var(--border-color); border-radius: var(--radius-lg, 8px); background: #f7f9fc; }
.prompt-box pre { max-height: 180px; margin: 0 110px 0 0; overflow: auto; white-space: pre-wrap; color: #3f4d63; font: 12px/1.65 ui-monospace, SFMono-Regular, Consolas, monospace; }
.prompt-box :deep(.arco-btn) { position: absolute; top: 12px; right: 12px; }
.external-panel__error { margin: 0; padding: 10px 12px; border-radius: var(--radius-lg, 8px); color: #b42318; background: #fff1f0; }
footer { display: flex; justify-content: space-between; gap: 10px; }
</style>
