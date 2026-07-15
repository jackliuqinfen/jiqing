<template>
  <AModal
    :visible="visible"
    :footer="false"
    :mask-closable="false"
    :esc-to-close="false"
    :width="1180"
    modal-class="contract-entry-modal"
    @cancel="requestClose"
  >
    <template #title>上传合同创建项目</template>

    <DocumentReviewWorkspace
      v-if="phase === 'review' && reviewId"
      :review-id="reviewId"
      @created="handleCreated"
    />

    <section v-else class="contract-entry">
      <header class="contract-entry__head">
        <span>合同驱动建档</span>
        <h3>上传施工合同，AI 自动预填项目资料</h3>
        <p>系统先识别合同，再由人工核对关键字段。确认前不会写入项目主档案。</p>
      </header>

      <div v-if="phase === 'select'" class="upload-panel">
        <label class="upload-drop" :class="{ 'upload-drop--ready': file }">
          <input type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp" @change="pickFile" />
          <span class="upload-drop__icon">↑</span>
          <strong>{{ file ? file.name : '选择扫描合同文件' }}</strong>
          <small>{{ file ? formatFileSize(file.size) : '支持 PDF、PNG、JPG、TIFF、WebP' }}</small>
        </label>
        <div class="contract-entry__actions">
          <AButton variant="outline" @click="requestClose">取消</AButton>
          <AButton theme="primary" :disabled="!file" @click="uploadAndRecognize">开始识别</AButton>
        </div>
      </div>

      <div v-else-if="phase === 'uploading' || phase === 'recognizing'" class="processing-panel">
        <div class="processing-ring"><span>{{ phase === 'uploading' ? `${uploadProgress}%` : 'AI' }}</span></div>
        <h4>{{ phase === 'uploading' ? '正在安全上传合同' : '正在解析合同内容' }}</h4>
        <p>{{ phase === 'uploading' ? '上传完成后将自动进行 300 DPI 页面解析。' : '正在识别建设单位、施工单位、项目经理、合同金额、日期和付款条款。' }}</p>
        <div class="progress-track"><span :style="{ width: `${phase === 'uploading' ? uploadProgress : 78}%` }" /></div>
      </div>

      <div v-else class="result-panel" :class="`result-panel--${phase}`">
        <strong>{{ phase === 'manual' ? manualRequiredTitle(job) : '合同处理未完成' }}</strong>
        <p>{{ resultMessage }}</p>
        <div class="contract-entry__actions">
          <AButton variant="outline" @click="reset">重新选择合同</AButton>
          <AButton
            v-if="job && (phase === 'manual' || phase === 'failed')"
            theme="primary"
            @click="retryCurrentJob"
          >重新识别</AButton>
          <AButton v-else-if="phase === 'failed'" theme="primary" @click="uploadAndRecognize">重试上传</AButton>
        </div>
      </div>
    </section>
  </AModal>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import DocumentReviewWorkspace from './DocumentReviewWorkspace.vue'
import { fetchRecognitionJob, retryRecognition, startRecognition, uploadDocument } from '@/api/documentReview'
import { friendlyErrorMessage } from '@/utils/errors'
import type { RecognitionJob } from '@/types/documentReview'

type EntryPhase = 'select' | 'uploading' | 'recognizing' | 'review' | 'manual' | 'failed'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  'update:visible': [visible: boolean]
  created: [projectId: string]
}>()

const phase = ref<EntryPhase>('select')
const file = ref<File | null>(null)
const uploadProgress = ref(0)
const job = ref<RecognitionJob | null>(null)
const reviewId = ref('')
const resultMessage = ref('')
let pollTimer = 0

watch(() => props.visible, (visible) => {
  if (visible) reset()
  else stopPolling()
})

function pickFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null
}

async function uploadAndRecognize() {
  if (!file.value) return
  stopPolling()
  phase.value = 'uploading'
  uploadProgress.value = 0
  resultMessage.value = ''
  try {
    const uploaded = await uploadDocument(
      {
        file: file.value,
        documentType: 'construction_contract',
        lifecycleStage: 'contract_handoff',
      },
      (percent) => { uploadProgress.value = percent },
    )
    phase.value = 'recognizing'
    job.value = await startRecognition({
      documentVersionId: uploaded.version.id,
      schemaVersion: 'contract.v1',
      idempotencyKey: `contract-recognition:${uploaded.version.id}`,
    })
    handleJob(job.value)
  } catch (error) {
    phase.value = 'failed'
    resultMessage.value = friendlyErrorMessage(error, '合同上传或识别启动失败，请检查文件后重试。')
  }
}

function schedulePoll() {
  stopPolling()
  pollTimer = window.setTimeout(pollRecognition, 1600)
}

async function pollRecognition() {
  if (!job.value || !props.visible) return
  try {
    job.value = await fetchRecognitionJob(job.value.id)
    handleJob(job.value)
  } catch (error) {
    phase.value = 'failed'
    resultMessage.value = friendlyErrorMessage(error, '识别进度查询失败，请稍后重试。')
  }
}

async function retryCurrentJob() {
  if (!job.value) return
  stopPolling()
  phase.value = 'recognizing'
  resultMessage.value = ''
  try {
    job.value = await retryRecognition(job.value.id, {
      idempotencyKey: `contract-recognition-retry:${job.value.id}:${Date.now()}`,
    })
    handleJob(job.value)
  } catch (error) {
    phase.value = 'failed'
    resultMessage.value = friendlyErrorMessage(error, '重新识别启动失败，请稍后重试。')
  }
}

function handleJob(current: RecognitionJob) {
  if (current.status === 'queued' || current.status === 'running') {
    phase.value = 'recognizing'
    schedulePoll()
    return
  }
  stopPolling()
  if (current.status === 'review_ready' && current.reviewId) {
    reviewId.value = current.reviewId
    phase.value = 'review'
    return
  }
  if (current.status === 'manual_required') {
    phase.value = 'manual'
    resultMessage.value = manualRequiredMessage(current)
    return
  }
  phase.value = 'failed'
  resultMessage.value = current.error?.message || '合同识别失败，请重新上传清晰扫描件后重试。'
}

function manualRequiredMessage(current: RecognitionJob) {
  const code = current.error?.code || ''
  if (code === 'ocr_provider_not_configured') {
    return '合同已安全保存，但当前服务器尚未配置可用的 OCR 服务。请联系管理员配置后重新识别。'
  }
  if (code === 'ocr_page_quality_low') {
    return '扫描件清晰度不足，建议重新扫描后上传；也可以先点击重新识别再次尝试。'
  }
  if (code === 'ocr_provider_malformed_response') {
    return 'OCR 返回的版面信息暂时无法处理，请点击重新识别。若仍失败，请重新扫描该合同。'
  }
  return current.error?.message || 'AI 未能完成当前合同识别，请点击重新识别或重新上传清晰扫描件。'
}

function manualRequiredTitle(current: RecognitionJob | null) {
  if (current?.error?.code === 'ocr_provider_not_configured') return 'AI 识别服务尚未配置'
  if (current?.error?.code === 'ocr_page_quality_low') return '扫描件清晰度不足'
  return '合同识别需要重新处理'
}

function handleCreated(projectId: string) {
  emit('created', projectId)
  emit('update:visible', false)
}

function requestClose() {
  if (phase.value === 'uploading' || phase.value === 'recognizing') return
  emit('update:visible', false)
}

function reset() {
  stopPolling()
  phase.value = 'select'
  file.value = null
  uploadProgress.value = 0
  job.value = null
  reviewId.value = ''
  resultMessage.value = ''
}

function stopPolling() {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = 0
}

function formatFileSize(size: number) {
  return size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(size / 1024))} KB`
}

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.contract-entry { min-height: 590px; display: grid; align-content: center; gap: 28px; padding: 32px 56px; }
.contract-entry__head { max-width: 700px; margin: 0 auto; text-align: center; }
.contract-entry__head span { color: var(--primary-color); font-size: 12px; font-weight: 700; }
.contract-entry__head h3 { margin: 8px 0; font-size: 26px; }
.contract-entry__head p, .processing-panel p, .result-panel p { margin: 0; color: var(--text-secondary); }
.upload-panel, .processing-panel, .result-panel { width: min(720px, 100%); margin: 0 auto; }
.upload-drop { min-height: 220px; display: grid; place-content: center; gap: 10px; text-align: center; border: 1px dashed #b8c6dc; border-radius: var(--radius-lg, 8px); background: rgba(246,249,253,.86); cursor: pointer; }
.upload-drop:hover, .upload-drop--ready { border-color: var(--primary-color); background: rgba(22,93,255,.04); }
.upload-drop input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.upload-drop__icon { width: 42px; height: 42px; display: grid; place-content: center; margin: 0 auto; border-radius: 50%; color: #fff; background: var(--primary-color); font-size: 22px; }
.upload-drop small { color: var(--text-secondary); }
.contract-entry__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.processing-panel, .result-panel { min-height: 280px; display: grid; place-content: center; justify-items: center; gap: 12px; text-align: center; }
.processing-ring { width: 74px; height: 74px; display: grid; place-content: center; border: 6px solid #dce7f9; border-top-color: var(--primary-color); border-radius: 50%; animation: spin 1.1s linear infinite; }
.processing-ring span { animation: counter-spin 1.1s linear infinite; font-weight: 700; }
.progress-track { width: 420px; max-width: 80vw; height: 6px; overflow: hidden; border-radius: 3px; background: #e7edf6; }
.progress-track span { display: block; height: 100%; background: var(--primary-color); transition: width .25s ease; }
.result-panel { padding: 28px; border: 1px solid var(--border-color); border-radius: var(--radius-lg, 8px); background: #fff; }
.result-panel--manual { border-color: #ffe1a8; background: #fffdf5; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes counter-spin { to { transform: rotate(-360deg); } }
</style>
