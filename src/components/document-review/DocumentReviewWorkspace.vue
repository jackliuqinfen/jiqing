<template>
  <section class="review-workspace">
    <header class="review-head">
      <div>
        <span class="review-head__eyebrow">AI 识别复核</span>
        <h3>对照合同原文确认项目资料</h3>
        <p>关键字段必须逐项确认。系统只在确认后创建项目，不会直接写入识别结果。</p>
      </div>
      <AButton variant="outline" :loading="loading" @click="loadReview">刷新识别结果</AButton>
    </header>

    <div v-if="loading" class="review-state">正在加载合同复核数据...</div>
    <div v-else-if="errorMessage" class="review-state review-state--error">
      <strong>复核数据加载失败</strong>
      <span>{{ errorMessage }}</span>
      <AButton variant="outline" @click="loadReview">重试</AButton>
    </div>

    <div v-else-if="review" class="review-grid">
      <section class="source-pane">
        <div class="pane-toolbar">
          <div>
            <strong>合同原文</strong>
            <span>第 {{ currentPageIndex + 1 }} / {{ review.pages.length }} 页</span>
          </div>
          <div class="pane-toolbar__actions">
            <AButton size="small" variant="text" :disabled="currentPageIndex <= 0" @click="currentPageIndex--">上一页</AButton>
            <AButton size="small" variant="text" :disabled="currentPageIndex >= review.pages.length - 1" @click="currentPageIndex++">下一页</AButton>
            <AButton size="small" variant="text" @click="zoom = Math.max(0.6, zoom - 0.1)">-</AButton>
            <span>{{ Math.round(zoom * 100) }}%</span>
            <AButton size="small" variant="text" @click="zoom = Math.min(1.6, zoom + 0.1)">+</AButton>
          </div>
        </div>
        <div class="page-stage">
          <div v-if="pageLoading" class="page-placeholder">正在载入合同页面...</div>
          <div v-else-if="!pageUrl" class="page-placeholder">当前页面暂不可预览</div>
          <div v-else class="page-canvas" :style="{ width: `${zoom * 100}%` }">
            <img :src="pageUrl" :alt="`合同第 ${currentPageIndex + 1} 页`" />
            <span
              v-for="(anchor, index) in visibleAnchors"
              :key="`${anchor.id}-${index}`"
              class="evidence-box"
              :style="anchorStyle(anchor.bbox)"
              :title="anchor.sourceText"
            />
          </div>
        </div>
      </section>

      <section class="field-pane">
        <div class="pane-toolbar pane-toolbar--fields">
          <div>
            <strong>识别字段</strong>
            <span>{{ resolvedCriticalCount }} / {{ criticalFields.length }} 个关键字段已确认</span>
          </div>
          <span v-if="review.blockers.length" class="blocker-count">{{ review.blockers.length }} 项待处理</span>
          <span v-else class="ready-count">可以生成项目</span>
        </div>

        <div v-if="review.blockers.length" class="blocker-panel">
          <strong>确认前还需处理</strong>
          <span v-for="issue in review.blockers" :key="`${issue.code}-${issue.field}`">
            {{ fieldLabel(issue.field) }}：{{ issue.message }}
          </span>
        </div>

        <div class="field-list">
          <section v-for="section in review.sections" :key="section.key" class="field-section">
            <h4>{{ sectionLabel(section.key) }}</h4>
            <article
              v-for="field in section.fields"
              :key="field.id"
              class="field-card"
              :class="{
                'field-card--critical': isCritical(field.semanticKey),
                'field-card--active': activeFieldId === field.id,
              }"
              @click="focusField(field)"
            >
              <div class="field-card__head">
                <label>
                  {{ fieldLabel(field.semanticKey) }}
                  <span v-if="isCritical(field.semanticKey)">必核</span>
                </label>
                <small :class="confidenceClass(field.confidence)">{{ confidenceText(field.confidence) }}</small>
              </div>
              <ATextarea
                v-if="isMultilineField(field.semanticKey)"
                v-model="drafts[field.id]"
                :auto-size="{ minRows: 2, maxRows: 5 }"
                :disabled="savingFieldId === field.id || review.status === 'confirmed'"
                placeholder="未识别，请核对合同原文"
                @click.stop
              />
              <AInput
                v-else
                v-model="drafts[field.id]"
                :disabled="savingFieldId === field.id || review.status === 'confirmed'"
                :placeholder="isMoneyField(field.semanticKey) ? '请输入金额（元）' : '未识别，请核对合同原文'"
                @click.stop
              />
              <div class="field-card__meta">
                <span v-if="field.anchors.length">已定位合同原文</span>
                <span v-else class="field-card__missing">未定位原文</span>
                <span v-if="field.decision">{{ decisionLabel(field.decision.decision) }}</span>
              </div>
              <div v-if="review.status !== 'confirmed'" class="field-card__actions" @click.stop>
                <AButton
                  size="small"
                  variant="outline"
                  :loading="savingFieldId === field.id && savingMode === 'accepted'"
                  :disabled="!hasAiValue(field.aiValue)"
                  @click="saveField(field, 'accepted')"
                >采用识别值</AButton>
                <AButton
                  size="small"
                  theme="primary"
                  :loading="savingFieldId === field.id && savingMode === 'modified'"
                  :disabled="!drafts[field.id]?.trim()"
                  @click="saveField(field, 'modified')"
                >保存修改</AButton>
              </div>
            </article>
          </section>
        </div>

        <footer class="confirm-bar">
          <label class="confirm-check">
            <input v-model="confirmedByHuman" type="checkbox" />
            <span>我已对照合同原文核对以上关键字段</span>
          </label>
          <AButton
            theme="primary"
            :loading="confirming"
            :disabled="!canConfirm"
            @click="confirmProject"
          >确认并创建项目</AButton>
        </footer>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { MessagePlugin } from '@/ui/message'
import {
  confirmDocumentReview,
  fetchDocumentPageBlob,
  fetchDocumentReview,
  saveReviewDecisions,
} from '@/api/documentReview'
import { buildReviewDecisionInput } from '@/utils/documentReviewDecision'
import { friendlyErrorMessage } from '@/utils/errors'
import type {
  DocumentReview,
  EvidenceAnchor,
  EvidenceBox,
  ExtractedField,
  JsonValue,
  ReviewDecisionType,
} from '@/types/documentReview'

const props = defineProps<{ reviewId: string }>()
const emit = defineEmits<{ created: [projectId: string] }>()

const review = shallowRef<DocumentReview | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const currentPageIndex = ref(0)
const pageUrl = ref('')
const pageLoading = ref(false)
const zoom = ref(0.9)
const activeFieldId = ref('')
const drafts = reactive<Record<string, string>>({})
const savingFieldId = ref('')
const savingMode = ref<ReviewDecisionType | ''>('')
const confirmedByHuman = ref(false)
const confirming = ref(false)

const criticalSemanticKeys = new Set([
  'project.name',
  'party.owner',
  'party.contractor',
  'contract.amount',
  'contract.signed_date',
  'contract.payment_terms',
])

const criticalFields = computed<ExtractedField[]>(() => {
  const result: ExtractedField[] = []
  for (const section of review.value?.sections || []) {
    for (const field of section.fields) {
      if (isCritical(field.semanticKey)) result.push(field)
    }
  }
  return result
})
const resolvedCriticalCount = computed(() =>
  criticalFields.value.filter((field) => ['accepted', 'modified'].includes(field.decision?.decision || '')).length,
)
const activeField = computed<ExtractedField | undefined>(() => {
  for (const section of review.value?.sections || []) {
    const field = section.fields.find((item) => item.id === activeFieldId.value)
    if (field) return field
  }
  return undefined
})
const currentPage = computed(() => review.value?.pages[currentPageIndex.value] || null)
const visibleAnchors = computed(() => {
  const pageId = currentPage.value?.id
  return (activeField.value?.anchors || []).filter((anchor) => anchor.pageId === pageId)
})
const canConfirm = computed(() =>
  Boolean(
    review.value &&
      confirmedByHuman.value &&
      review.value.blockers.length === 0 &&
      review.value.allowedCommands.includes('confirm'),
  ),
)

watch(() => props.reviewId, loadReview, { immediate: true })
watch(currentPageIndex, loadPage)

async function loadReview() {
  if (!props.reviewId) return
  loading.value = true
  errorMessage.value = ''
  try {
    review.value = await fetchDocumentReview(props.reviewId)
    hydrateDrafts()
    if (!activeFieldId.value) activeFieldId.value = criticalFields.value[0]?.id || ''
    const anchorPageId = activeField.value?.anchors[0]?.pageId
    if (anchorPageId) {
      const index = review.value.pages.findIndex((page) => page.id === anchorPageId)
      if (index >= 0) currentPageIndex.value = index
    }
    await loadPage()
  } catch (error) {
    errorMessage.value = friendlyErrorMessage(error, '无法加载合同复核数据')
  } finally {
    loading.value = false
  }
}

function hydrateDrafts() {
  for (const section of review.value?.sections || []) {
    for (const field of section.fields) {
      const value = field.decision?.confirmedValue ?? field.aiValue
      drafts[field.id] = valueForInput(field.semanticKey, value)
    }
  }
}

async function loadPage() {
  const page = currentPage.value
  if (!page || !review.value) return
  pageLoading.value = true
  revokePageUrl()
  try {
    const versionId = page.imageUrl.split('/')[3] || ''
    const blob = await fetchDocumentPageBlob(versionId, page.pageNumber)
    pageUrl.value = URL.createObjectURL(blob)
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '合同页面预览失败'))
  } finally {
    pageLoading.value = false
  }
}

function focusField(field: ExtractedField) {
  activeFieldId.value = field.id
  const pageId = field.anchors[0]?.pageId
  if (!pageId || !review.value) return
  const index = review.value.pages.findIndex((page) => page.id === pageId)
  if (index >= 0) currentPageIndex.value = index
}

async function saveField(field: ExtractedField, decision: 'accepted' | 'modified') {
  if (!review.value) return
  savingFieldId.value = field.id
  savingMode.value = decision
  try {
    const modifiedValue = parseInputValue(field.semanticKey, drafts[field.id])
    review.value = await saveReviewDecisions(review.value.id, {
      expectedReviewVersion: review.value.reviewVersion,
      decisions: [buildReviewDecisionInput(field, decision, modifiedValue)],
    })
    hydrateDrafts()
    MessagePlugin.success(`${fieldLabel(field.semanticKey)}已确认`)
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '字段保存失败，请刷新后重试'))
    await loadReview()
  } finally {
    savingFieldId.value = ''
    savingMode.value = ''
  }
}

async function confirmProject() {
  if (!review.value || !canConfirm.value) return
  confirming.value = true
  try {
    const result = await confirmDocumentReview(review.value.id, {
      expectedReviewVersion: review.value.reviewVersion,
      idempotencyKey: `contract-confirm:${review.value.id}:${review.value.reviewVersion}`,
      formTemplateVersion: 'contract.v1',
    })
    if (!result.projectId) throw new Error('项目创建结果缺少项目编号')
    MessagePlugin.success('合同已确认，项目主档案已创建')
    emit('created', result.projectId)
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '项目创建失败，请检查阻断项后重试'))
    await loadReview()
  } finally {
    confirming.value = false
  }
}

function valueForInput(key: string, value: JsonValue): string {
  if (value === null || value === undefined) return ''
  if (isMoneyField(key) && typeof value === 'number') return (value / 100).toFixed(2)
  if (Array.isArray(value)) return value.map(String).join('\n')
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function parseInputValue(key: string, value: string): JsonValue {
  const text = value.trim()
  if (isMoneyField(key)) return Math.round(Number(text || 0) * 100)
  if (isMultilineField(key)) return text.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
  return text
}

function fieldLabel(key: string) {
  return ({
    'project.name': '项目名称',
    'party.owner': '建设单位',
    'party.contractor': '施工单位',
    'project.manager': '项目经理',
    'contract.number': '合同编号',
    'contract.type': '合同类型',
    'contract.amount': '合同金额（元）',
    'contract.signed_date': '合同签订日期',
    'contract.start_date': '计划开工日期',
    'contract.end_date': '计划完工日期',
    'contract.payment_terms': '付款条款',
    'contract.retention_terms': '质保条款',
    'contract.performance_bond_terms': '履约保证条款',
  } as Record<string, string>)[key] || key
}

function sectionLabel(key: string) {
  return ({ project: '项目信息', party: '参建单位', contract: '合同信息' } as Record<string, string>)[key] || '其他信息'
}

function isCritical(key: string) {
  return criticalSemanticKeys.has(key)
}

function isMoneyField(key: string) {
  return key === 'contract.amount'
}

function isMultilineField(key: string) {
  return key.endsWith('_terms')
}

function hasAiValue(value: JsonValue) {
  return value !== null && value !== '' && (!Array.isArray(value) || value.length > 0)
}

function decisionLabel(decision: ReviewDecisionType) {
  return ({ accepted: '已采用', modified: '已修改', rejected: '已驳回', unrecognized: '未识别' } as Record<string, string>)[decision]
}

function confidenceText(confidence: number | null) {
  if (confidence === null) return '待核对'
  return `置信度 ${Math.round(confidence * 100)}%`
}

function confidenceClass(confidence: number | null) {
  if (confidence === null || confidence < 0.7) return 'confidence confidence--low'
  return 'confidence'
}

function anchorStyle(bbox: EvidenceBox) {
  return {
    left: `${bbox[0] * 100}%`,
    top: `${bbox[1] * 100}%`,
    width: `${bbox[2] * 100}%`,
    height: `${bbox[3] * 100}%`,
  }
}

function revokePageUrl() {
  if (pageUrl.value) URL.revokeObjectURL(pageUrl.value)
  pageUrl.value = ''
}

onBeforeUnmount(revokePageUrl)
</script>

<style scoped>
.review-workspace { min-height: 640px; color: var(--text-primary); }
.review-head, .pane-toolbar, .field-card__head, .field-card__meta, .field-card__actions, .confirm-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.review-head { padding: 0 0 16px; border-bottom: 1px solid var(--border-color); }
.review-head h3 { margin: 4px 0; font-size: 20px; }
.review-head p, .pane-toolbar span, .field-card__meta { margin: 0; color: var(--text-secondary); font-size: 12px; }
.review-head__eyebrow { color: var(--primary-color); font-size: 12px; font-weight: 700; }
.review-grid { display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(420px, .92fr); gap: 16px; padding-top: 16px; min-height: 590px; }
.source-pane, .field-pane { min-width: 0; overflow: hidden; border: 1px solid var(--border-color); border-radius: var(--radius-lg, 8px); background: rgba(255,255,255,.9); }
.source-pane, .field-pane { display: flex; flex-direction: column; }
.pane-toolbar { min-height: 54px; padding: 10px 14px; border-bottom: 1px solid var(--border-color); }
.pane-toolbar > div:first-child { display: flex; flex-direction: column; gap: 3px; }
.pane-toolbar__actions { display: flex; align-items: center; gap: 4px; }
.page-stage { flex: 1; overflow: auto; padding: 18px; background: #eef2f7; }
.page-canvas { position: relative; min-width: 420px; margin: 0 auto; box-shadow: 0 8px 24px rgba(15,35,70,.12); }
.page-canvas img { display: block; width: 100%; height: auto; background: #fff; }
.evidence-box { position: absolute; border: 2px solid rgba(22,93,255,.9); background: rgba(22,93,255,.12); pointer-events: none; }
.page-placeholder, .review-state { min-height: 360px; display: grid; place-content: center; gap: 12px; text-align: center; color: var(--text-secondary); }
.review-state--error { color: var(--danger-color); }
.field-pane { max-height: 690px; }
.field-list { flex: 1; overflow: auto; padding: 12px; }
.field-section h4 { margin: 10px 2px 8px; font-size: 14px; }
.field-section:first-child h4 { margin-top: 0; }
.field-card { margin-bottom: 8px; padding: 12px; border: 1px solid var(--border-color); border-radius: var(--radius-md, 6px); background: #fff; cursor: pointer; }
.field-card--active { border-color: rgba(22,93,255,.55); box-shadow: 0 0 0 2px rgba(22,93,255,.08); }
.field-card--critical { border-left: 3px solid var(--primary-color); }
.field-card__head { margin-bottom: 8px; }
.field-card__head label { font-weight: 650; }
.field-card__head label span { margin-left: 6px; color: var(--primary-color); font-size: 11px; }
.field-card__meta { margin-top: 7px; }
.field-card__actions { justify-content: flex-end; margin-top: 8px; }
.field-card__missing, .confidence--low, .blocker-count { color: #d46b08 !important; }
.confidence { color: #0f8f70; font-size: 11px; }
.blocker-panel { display: grid; gap: 4px; margin: 10px 12px 0; padding: 10px 12px; border-left: 3px solid #faad14; background: #fffbe6; font-size: 12px; }
.ready-count { color: #0f8f70; font-size: 12px; font-weight: 650; }
.confirm-bar { padding: 12px 14px; border-top: 1px solid var(--border-color); background: #fff; }
.confirm-check { display: flex; align-items: center; gap: 8px; font-size: 12px; }
@media (max-width: 980px) { .review-grid { grid-template-columns: 1fr; } .field-pane { max-height: none; } }
</style>
