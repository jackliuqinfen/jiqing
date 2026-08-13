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
    <template #title>手工创建项目</template>

    <DocumentReviewWorkspace
      v-if="phase === 'review' && reviewId"
      :review-id="reviewId"
      @created="handleCreated"
    />

    <section v-else class="contract-entry">
      <header class="contract-entry__head">
        <span>手工建档</span>
        <h3>填写合同与项目信息，再由人工确认创建项目</h3>
        <p>可以先保存录入草稿；确认前不会写入项目主档案。</p>
      </header>

      <ContractEntryMode
        v-if="phase === 'mode'"
        :drafts="editableDrafts"
        :loading="draftsLoading"
        @select="selectMode"
        @resume="resumeDraft"
        @abandon="abandonDraft"
      />

      <div v-else-if="phase === 'input' && mode === 'system'" class="upload-panel">
        <label class="upload-drop" :class="{ 'upload-drop--ready': file }">
          <input type="file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp" @change="pickFile" />
          <span class="upload-drop__icon">↑</span>
          <strong>{{ file ? file.name : '选择扫描合同文件' }}</strong>
          <small>{{ file ? formatFileSize(file.size) : '支持 PDF、PNG、JPG、TIFF、WebP' }}</small>
        </label>
        <p v-if="resultMessage" class="inline-error">{{ resultMessage }}</p>
        <div class="contract-entry__actions contract-entry__actions--split">
          <AButton variant="outline" @click="backToModes">返回选择</AButton>
          <AButton theme="primary" :disabled="!file" @click="uploadAndRecognize">开始识别</AButton>
        </div>
      </div>

      <ExternalAiImportPanel
        v-else-if="phase === 'input' && mode === 'external'"
        :file-name="file?.name || ''"
        :source-ready="sourceReady"
        :markdown="externalMarkdown"
        :prompt="externalPrompt"
        :copied="promptCopied"
        :busy="busyAction === 'external'"
        :error-message="resultMessage"
        @file="setFile"
        @copy="copyPrompt"
        @back="backToModes"
        @submit="submitExternal"
        @update:markdown="externalMarkdown = $event"
      />

      <ManualContractDraftPanel
        v-else-if="phase === 'input' && mode === 'manual'"
        :values="manualValues"
        :file-name="file?.name || ''"
        :source-ready="sourceReady"
        :busy="!!busyAction"
        :action="busyAction === 'draft' || busyAction === 'manual-review' ? (busyAction === 'draft' ? 'draft' : 'review') : ''"
        :notice="resultMessage"
        @file="setFile"
        @back="backToModes"
        @save-draft="saveManualDraft"
        @start-review="submitManualReview"
        @update-field="updateManualField"
      />

      <div v-else-if="phase === 'uploading' || phase === 'recognizing'" class="processing-panel">
        <div class="processing-ring"><span>{{ phase === 'uploading' ? `${uploadProgress}%` : 'AI' }}</span></div>
        <h4>{{ phase === 'uploading' ? '正在安全上传合同' : '正在解析合同内容' }}</h4>
        <p>{{ phase === 'uploading' ? '上传完成后将生成 300 DPI 页面，供人工对照复核。' : '正在识别建设单位、施工单位、项目经理、合同金额、日期和付款条款。' }}</p>
        <div class="progress-track"><span :style="{ width: `${phase === 'uploading' ? uploadProgress : 78}%` }" /></div>
      </div>

      <div v-else class="result-panel" :class="`result-panel--${phase}`">
        <strong>{{ phase === 'recovery' ? manualRequiredTitle(job) : '合同处理未完成' }}</strong>
        <p>{{ resultMessage }}</p>
        <div class="recovery-options">
          <AButton v-if="job" variant="outline" @click="retryCurrentJob">重新识别</AButton>
          <AButton v-if="projectIntakeFeatures.externalAiImport" variant="outline" @click="selectMode('external')">粘贴外部 AI 结果</AButton>
          <AButton theme="primary" @click="selectMode('manual')">转为手工录入</AButton>
        </div>
        <AButton variant="text" @click="reset">重新选择合同</AButton>
      </div>
    </section>
  </AModal>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import ContractEntryMode from './ContractEntryMode.vue'
import DocumentReviewWorkspace from './DocumentReviewWorkspace.vue'
import ExternalAiImportPanel from './ExternalAiImportPanel.vue'
import ManualContractDraftPanel from './ManualContractDraftPanel.vue'
import {
  abandonProjectIntakeDraft,
  createProjectIntakeDraft,
  fetchRecognitionJob,
  importDirectExternalResult,
  importJobExternalResult,
  listProjectIntakeDrafts,
  retryRecognition,
  startDirectManualReview,
  startJobManualReview,
  startRecognition,
  saveProjectIntakeDraft,
  uploadDocument,
} from '@/api/documentReview'
import { MessagePlugin } from '@/ui/message'
import { friendlyErrorMessage } from '@/utils/errors'
import { projectIntakeFeatures } from '@/config/projectIntakeFeatures'
import type { ContractDraftValues, ProjectIntakeDraft, RecognitionJob } from '@/types/documentReview'

type EntryMode = 'system' | 'external' | 'manual'
type EntryPhase = 'mode' | 'input' | 'uploading' | 'recognizing' | 'review' | 'recovery' | 'failed'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  'update:visible': [visible: boolean]
  created: [projectId: string]
}>()

const phase = ref<EntryPhase>('mode')
const mode = ref<EntryMode | null>(null)
const file = ref<File | null>(null)
const uploadedDocumentId = ref('')
const uploadedVersionId = ref('')
const uploadProgress = ref(0)
const job = ref<RecognitionJob | null>(null)
const reviewId = ref('')
const resultMessage = ref('')
const externalMarkdown = ref('')
const promptCopied = ref(false)
const busyAction = ref<'external' | 'draft' | 'manual-review' | ''>('')
const manualValues = reactive<ContractDraftValues>({})
const recentDrafts = ref<ProjectIntakeDraft[]>([])
const draftsLoading = ref(false)
const activeDraftId = ref('')
const activeDraftRevision = ref<number | null>(null)
let pollTimer = 0

const sourceReady = computed(() => !!uploadedVersionId.value || !!job.value)
const editableDrafts = computed(() => recentDrafts.value.filter((draft) => draft.status === 'draft' || draft.status === 'document_attached'))
const canFallbackFromJob = computed(() => job.value?.status === 'manual_required' || job.value?.status === 'failed')

const externalPrompt = `你是一名严谨的中国施工合同信息提取助手。请阅读我上传的施工合同扫描件，只提取合同原文明确存在的信息，不得推测、补全或编造。找不到的字段请填写空字符串。金额保留原文单位，日期统一为 YYYY-MM-DD；付款条款、质保金条款、履约保证金条款尽量保留完整原文。

只输出一个 Markdown 的 json 代码块，不要输出解释。结构必须严格如下：
\`\`\`json
{
  "schemaVersion": "contract.v1",
  "fields": {
    "project.name": { "value": "", "evidence": "", "page": 1 },
    "party.owner": { "value": "", "evidence": "", "page": 1 },
    "party.contractor": { "value": "", "evidence": "", "page": 1 },
    "contract.number": { "value": "", "evidence": "", "page": 1 },
    "contract.type": { "value": "", "evidence": "", "page": 1 },
    "contract.amount": { "value": "", "evidence": "", "page": 1 },
    "contract.signed_date": { "value": "", "evidence": "", "page": 1 },
    "contract.start_date": { "value": "", "evidence": "", "page": 1 },
    "contract.end_date": { "value": "", "evidence": "", "page": 1 },
    "project.manager": { "value": "", "evidence": "", "page": 1 },
    "contract.payment_terms": { "value": "", "evidence": "", "page": 1 },
    "contract.retention_terms": { "value": "", "evidence": "", "page": 1 },
    "contract.performance_bond_terms": { "value": "", "evidence": "", "page": 1 }
  }
}
\`\`\`

规则：没有原文依据的字段必须留空；page 必须是对应原文所在的正整数页码；不要增加任何字段。`

watch(() => props.visible, (visible) => {
  if (visible) {
    reset()
    void loadDrafts()
  }
  else stopPolling()
})

function selectMode(nextMode: EntryMode) {
  mode.value = nextMode
  phase.value = 'input'
  resultMessage.value = ''
}

function backToModes() {
  if (busyAction.value) return
  mode.value = null
  phase.value = 'mode'
  setActiveDraft(null)
  resultMessage.value = ''
}

function pickFile(event: Event) {
  setFile((event.target as HTMLInputElement).files?.[0] || null)
}

function setFile(nextFile: File | null) {
  file.value = nextFile
  uploadedDocumentId.value = ''
  uploadedVersionId.value = ''
  job.value = null
  resultMessage.value = ''
}

async function ensureUploaded() {
  if (uploadedVersionId.value) return uploadedVersionId.value
  if (!file.value) throw new Error('请先选择合同扫描件。')
  phase.value = 'uploading'
  uploadProgress.value = 0
  const uploaded = await uploadDocument(
    {
      file: file.value,
      documentType: 'construction_contract',
      lifecycleStage: 'contract_handoff',
    },
    (percent) => { uploadProgress.value = percent },
  )
  uploadedDocumentId.value = uploaded.document.id
  uploadedVersionId.value = uploaded.version.id
  return uploaded.version.id
}

async function uploadAndRecognize() {
  if (!file.value) return
  stopPolling()
  resultMessage.value = ''
  try {
    const versionId = await ensureUploaded()
    phase.value = 'recognizing'
    job.value = await startRecognition({
      documentVersionId: versionId,
      schemaVersion: 'contract.v1',
      idempotencyKey: `contract-recognition:${versionId}`,
    })
    handleJob(job.value)
  } catch (error) {
    phase.value = 'failed'
    resultMessage.value = friendlyErrorMessage(error, '合同上传或识别启动失败，请检查文件后重试。')
  }
}

async function submitExternal() {
  busyAction.value = 'external'
  resultMessage.value = ''
  try {
    const payload = {
      idempotencyKey: `contract-external:${job.value?.id || uploadedVersionId.value || Date.now()}`,
      fallbackReason: canFallbackFromJob.value ? 'system_ai_unavailable' : 'external_ai_selected',
      markdown: externalMarkdown.value,
    }
    const result = canFallbackFromJob.value && job.value
      ? await importJobExternalResult(job.value.id, payload)
      : await importDirectExternalResult(await ensureUploaded(), payload)
    handleJob(result)
  } catch (error) {
    phase.value = 'input'
    resultMessage.value = friendlyErrorMessage(error, '外部 AI 结果无法解析，请检查 JSON 格式后重试。')
  } finally {
    busyAction.value = ''
  }
}

async function saveManualDraft() {
  busyAction.value = 'draft'
  resultMessage.value = ''
  try {
    let uploadFailure = ''
    if (file.value && !uploadedVersionId.value) {
      try {
        await ensureUploaded()
      } catch (error) {
        uploadFailure = friendlyErrorMessage(error, '所选合同暂未上传成功')
        phase.value = 'input'
      }
    }
    const payload = {
      values: { ...manualValues },
      fallbackReason: uploadFailure ? 'upload_failed_or_deferred' : (file.value ? 'manual_selected' : 'contract_not_available'),
      fallbackNote: uploadFailure || (file.value ? '用户选择手工录入合同信息' : '尚未取得合同文件，仅保存录入草稿'),
      documentId: uploadedDocumentId.value || undefined,
      documentVersionId: uploadedVersionId.value || undefined,
    }
    const draft = activeDraftId.value
      ? await saveProjectIntakeDraft(activeDraftId.value, {
          ...payload,
          expectedRevision: requireActiveDraftRevision(),
        })
      : await createProjectIntakeDraft(payload)
    setActiveDraft(draft)
    await loadDrafts()
    phase.value = 'input'
    resultMessage.value = uploadFailure
      ? `草稿已保存，但合同文件尚未上传成功：${uploadFailure}。网络恢复后可继续上传。`
      : draft.status === 'document_attached'
      ? '草稿已保存并关联合同。你可以继续进入人工复核。'
      : '草稿已保存。取得合同后再补充文件并进入复核。'
    MessagePlugin.success('合同录入草稿已保存')
  } catch (error) {
    phase.value = 'input'
    resultMessage.value = friendlyErrorMessage(error, '草稿保存失败，请稍后重试。')
  } finally {
    busyAction.value = ''
  }
}

async function submitManualReview() {
  busyAction.value = 'manual-review'
  resultMessage.value = ''
  try {
    const payload = {
      idempotencyKey: `contract-manual:${job.value?.id || uploadedVersionId.value || Date.now()}`,
      fallbackReason: canFallbackFromJob.value ? 'system_ai_unavailable' : 'manual_selected',
      values: { ...manualValues },
    }
    const result = canFallbackFromJob.value && job.value
      ? await startJobManualReview(job.value.id, payload)
      : await startDirectManualReview(await ensureUploaded(), payload)
    handleJob(result)
  } catch (error) {
    phase.value = 'input'
    resultMessage.value = friendlyErrorMessage(error, '无法进入人工复核，请检查合同文件后重试。')
  } finally {
    busyAction.value = ''
  }
}

function updateManualField(key: string, value: string) {
  manualValues[key] = value
}

async function loadDrafts() {
  draftsLoading.value = true
  try {
    recentDrafts.value = await listProjectIntakeDrafts()
  } catch {
    recentDrafts.value = []
  } finally {
    draftsLoading.value = false
  }
}

function resumeDraft(draft: ProjectIntakeDraft) {
  setActiveDraft(draft)
  Object.keys(manualValues).forEach((key) => delete manualValues[key])
  Object.assign(manualValues, draft.values)
  file.value = null
  uploadedDocumentId.value = draft.documentId || ''
  uploadedVersionId.value = draft.documentVersionId || ''
  job.value = null
  mode.value = 'manual'
  phase.value = 'input'
  resultMessage.value = draft.status === 'document_attached' ? '已恢复草稿及其合同原件。' : '已恢复草稿，可继续补充合同。'
}

async function abandonDraft(draftId: string) {
  if (!window.confirm('确认放弃这条合同录入草稿？放弃后不能继续编辑。')) return
  const draft = recentDrafts.value.find((item) => item.id === draftId)
  if (!draft) {
    MessagePlugin.error('草稿已不在当前列表中，请刷新后重试。')
    return
  }
  try {
    await abandonProjectIntakeDraft(draftId, draft.revision)
    if (activeDraftId.value === draftId) setActiveDraft(null)
    await loadDrafts()
    MessagePlugin.success('草稿已放弃')
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '草稿放弃失败，请稍后重试。'))
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(externalPrompt)
    promptCopied.value = true
    MessagePlugin.success('提示词已复制')
  } catch {
    MessagePlugin.error('浏览器未允许复制，请手动选择提示词')
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
  job.value = current
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
    phase.value = 'recovery'
    resultMessage.value = manualRequiredMessage(current)
    return
  }
  phase.value = 'failed'
  resultMessage.value = current.error?.message || '合同识别失败，可改用外部 AI 或手工录入继续处理。'
}

function manualRequiredMessage(current: RecognitionJob) {
  const code = current.error?.code || ''
  if (code === 'ocr_provider_not_configured') return '合同已安全保存，但系统 AI 服务尚未就绪。你可以立即改用外部 AI 结果或手工录入。'
  if (code === 'ocr_page_quality_low') return '扫描件清晰度不足。可重新扫描，也可以转为外部 AI 或手工录入。'
  if (code === 'ocr_provider_malformed_response') return 'AI 返回结果暂时无法处理，可重新识别或改用备用录入方式。'
  return current.error?.message || 'AI 未能完成当前合同识别，请选择备用录入方式继续。'
}

function manualRequiredTitle(current: RecognitionJob | null) {
  if (current?.error?.code === 'ocr_provider_not_configured') return '系统 AI 暂不可用，合同已保存'
  if (current?.error?.code === 'ocr_page_quality_low') return '扫描件清晰度不足'
  return '请选择备用处理方式'
}

async function handleCreated(projectId: string) {
  if (activeDraftId.value) {
    try {
      const draft = await saveProjectIntakeDraft(activeDraftId.value, {
        expectedRevision: requireActiveDraftRevision(),
        completedProjectId: projectId,
      })
      setActiveDraft(draft)
    } catch {
      MessagePlugin.warning('项目已创建，但原录入草稿未能自动归档。')
    }
  }
  emit('created', projectId)
  emit('update:visible', false)
}

function requestClose() {
  if (phase.value === 'uploading' || phase.value === 'recognizing' || busyAction.value) return
  emit('update:visible', false)
}

function reset() {
  stopPolling()
  phase.value = 'mode'
  mode.value = null
  file.value = null
  uploadedDocumentId.value = ''
  uploadedVersionId.value = ''
  uploadProgress.value = 0
  job.value = null
  reviewId.value = ''
  resultMessage.value = ''
  externalMarkdown.value = ''
  promptCopied.value = false
  busyAction.value = ''
  setActiveDraft(null)
  Object.keys(manualValues).forEach((key) => delete manualValues[key])
}

function setActiveDraft(draft: ProjectIntakeDraft | null) {
  activeDraftId.value = draft?.id || ''
  activeDraftRevision.value = draft?.revision ?? null
}

function requireActiveDraftRevision() {
  if (activeDraftRevision.value === null) {
    throw new Error('当前草稿版本缺失，请重新载入草稿后继续。')
  }
  return activeDraftRevision.value
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
.contract-entry { min-height: 620px; display: grid; align-content: center; gap: 28px; padding: 30px 52px 38px; }
.contract-entry__head { max-width: 760px; margin: 0 auto; text-align: center; }
.contract-entry__head span { color: var(--primary-color); font-size: 12px; font-weight: 700; }
.contract-entry__head h3 { margin: 8px 0; font-size: 25px; }
.contract-entry__head p, .processing-panel p, .result-panel p { margin: 0; color: var(--text-secondary); }
.upload-panel, .processing-panel, .result-panel { width: min(760px, 100%); margin: 0 auto; }
.upload-drop { min-height: 220px; display: grid; place-content: center; gap: 10px; text-align: center; border: 1px dashed #b8c6dc; border-radius: var(--radius-lg, 8px); background: rgba(246,249,253,.86); cursor: pointer; }
.upload-drop:hover, .upload-drop--ready { border-color: var(--primary-color); background: rgba(22,93,255,.04); }
.upload-drop input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.upload-drop__icon { width: 42px; height: 42px; display: grid; place-content: center; margin: 0 auto; border-radius: 50%; color: #fff; background: var(--primary-color); font-size: 22px; }
.upload-drop small { color: var(--text-secondary); }
.contract-entry__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.contract-entry__actions--split { justify-content: space-between; }
.inline-error { margin: 12px 0 0; padding: 10px 12px; border-radius: var(--radius-lg, 8px); color: #b42318; background: #fff1f0; }
.processing-panel, .result-panel { min-height: 280px; display: grid; place-content: center; justify-items: center; gap: 12px; text-align: center; }
.processing-ring { width: 74px; height: 74px; display: grid; place-content: center; border: 6px solid #dce7f9; border-top-color: var(--primary-color); border-radius: 50%; animation: spin 1.1s linear infinite; }
.processing-ring span { animation: counter-spin 1.1s linear infinite; font-weight: 700; }
.progress-track { width: 420px; max-width: 80vw; height: 6px; overflow: hidden; border-radius: 3px; background: #e7edf6; }
.progress-track span { display: block; height: 100%; background: var(--primary-color); transition: width .25s ease; }
.result-panel { padding: 28px; border: 1px solid var(--border-color); border-radius: var(--radius-lg, 8px); background: rgba(255,255,255,.9); }
.result-panel--recovery { border-color: #f2d59b; background: #fffdf7; }
.recovery-options { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 8px; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes counter-spin { to { transform: rotate(-360deg); } }
</style>
