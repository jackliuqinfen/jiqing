<template>
  <AModal
    :visible="visible"
    title="推进项目阶段"
    :mask-closable="!submitting"
    :esc-to-close="!submitting"
    :closable="!submitting"
    :footer="false"
    width="520px"
    modal-class="project-stage-transition-modal"
    @cancel="visible = false"
  >
    <div class="transition-modal">
      <div class="transition-route">
        <div><span>当前阶段</span><strong>{{ snapshot?.currentStageLabel || '-' }}</strong></div>
        <span class="transition-route__arrow">→</span>
        <div><span>目标阶段</span><strong>{{ targetLabel || '-' }}</strong></div>
      </div>

      <AAlert v-if="errorMessage" type="error" :show-icon="true">
        {{ errorMessage }}
      </AAlert>

      <section class="transition-blockers" aria-label="推进校验结果">
        <div class="transition-blockers__head">
          <strong>推进校验</strong>
          <span v-if="validating">正在校验...</span>
          <span v-else-if="blockers.length">{{ blockers.length }} 项待处理</span>
          <span v-else>可推进</span>
        </div>
        <ul v-if="blockers.length">
          <li v-for="blocker in blockers" :key="`${blocker.code}-${blocker.field}`">
            <strong>{{ blocker.message }}</strong>
            <span>{{ blocker.field || blocker.code }}</span>
          </li>
        </ul>
        <p v-else-if="!validating">当前项目已满足后端校验条件。</p>
      </section>

      <label class="transition-reason">
        <span>推进原因</span>
        <ATextarea
          v-model="reason"
          :disabled="submitting"
          :auto-size="{ minRows: 2, maxRows: 4 }"
          :maxlength="500"
          placeholder="填写本次推进的依据或补充说明（选填）"
        />
      </label>

      <ACheckbox v-model="confirmed" :disabled="submitting || Boolean(blockers.length)">
        我已核对项目信息，确认将项目推进至“{{ targetLabel || '目标阶段' }}”。
      </ACheckbox>

      <div class="transition-modal__actions">
        <AButton :disabled="submitting" @click="visible = false">取消</AButton>
        <AButton v-if="needsRefresh" :loading="refreshing" @click="refreshAfterConflict">刷新状态</AButton>
        <AButton type="primary" :loading="submitting" :disabled="confirmDisabled" @click="submit">
          确认推进
        </AButton>
      </div>
    </div>
  </AModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  ProjectLifecycleApiError,
  transitionProjectLifecycle,
  validateProjectLifecycle,
} from '@/api/projectLifecycle'
import type {
  ProjectLifecycleBlocker,
  ProjectLifecycleSnapshot,
  ProjectLifecycleValidateResponse,
} from '@/types/projectLifecycle'
import { newIdempotencyKey } from '@/utils/idempotencyKey'

const props = defineProps<{
  visible: boolean
  projectId: string
  snapshot: ProjectLifecycleSnapshot | null
}>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  transitioned: [snapshot: ProjectLifecycleSnapshot]
  refresh: []
}>()

const visible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})
const validation = ref<ProjectLifecycleValidateResponse | null>(null)
const validating = ref(false)
const submitting = ref(false)
const refreshing = ref(false)
const reason = ref('')
const confirmed = ref(false)
const idempotencyKey = ref('')
const errorMessage = ref('')
const needsRefresh = ref(false)

const targetStage = computed(() => props.snapshot?.nextTransition?.toStage || '')
const targetLabel = computed(() => validation.value?.targetStageLabel || props.snapshot?.nextTransition?.toStageLabel || '')
const blockers = computed<ProjectLifecycleBlocker[]>(() => validation.value?.blockers || props.snapshot?.nextTransition?.blockers || [])
const confirmDisabled = computed(() => (
  submitting.value || validating.value || !validation.value?.canTransition || Boolean(blockers.value.length) || !confirmed.value
))

function resetSubmissionState() {
  validation.value = null
  reason.value = ''
  confirmed.value = false
  idempotencyKey.value = ''
  errorMessage.value = ''
  needsRefresh.value = false
}

async function validate() {
  if (!props.projectId || !targetStage.value) return
  validating.value = true
  errorMessage.value = ''
  needsRefresh.value = false
  try {
    validation.value = await validateProjectLifecycle(props.projectId, { toStage: targetStage.value })
  } catch (error) {
    errorMessage.value = lifecycleErrorMessage(error, '无法校验当前项目状态，请检查网络后重试。')
    validation.value = null
  } finally {
    validating.value = false
  }
}

async function submit() {
  if (confirmDisabled.value || !targetStage.value || !validation.value) return
  submitting.value = true
  errorMessage.value = ''
  needsRefresh.value = false
  // A failed request keeps this key so retrying the same user submission is idempotent.
  const key = idempotencyKey.value || (idempotencyKey.value = newIdempotencyKey('lifecycle'))
  try {
    const response = await transitionProjectLifecycle(props.projectId, {
      toStage: targetStage.value,
      expectedVersion: validation.value.currentVersion,
      idempotencyKey: key,
      reason: reason.value.trim(),
    })
    emit('transitioned', response.snapshot)
    visible.value = false
  } catch (error) {
    errorMessage.value = lifecycleErrorMessage(error, '推进失败，请检查网络后使用原信息重试。')
    needsRefresh.value = error instanceof ProjectLifecycleApiError && error.status === 409
    if (error instanceof ProjectLifecycleApiError && error.blockers.length) {
      validation.value = {
        ...validation.value,
        blockers: error.blockers,
        canTransition: false,
        currentVersion: error.currentVersion ?? validation.value.currentVersion,
      }
    }
  } finally {
    submitting.value = false
  }
}

async function refreshAfterConflict() {
  refreshing.value = true
  try {
    emit('refresh')
    visible.value = false
  } finally {
    refreshing.value = false
  }
}

function lifecycleErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ProjectLifecycleApiError) {
    if (error.status === 409) return '项目状态已由其他人更新，请刷新状态后再尝试推进。'
    return error.payload.error || fallback
  }
  return fallback
}

watch(visible, (opened) => {
  resetSubmissionState()
  if (opened) void validate()
})

watch(targetStage, (nextStage, previousStage) => {
  if (nextStage === previousStage) return
  resetSubmissionState()
  if (visible.value) void validate()
})
</script>

<style scoped>
.transition-modal { display: grid; gap: 16px; }
.transition-route { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 10px; align-items: center; padding: 10px; background: var(--color-gray-20); border: 1px solid var(--border-color); border-radius: 6px; }
.transition-route div { min-width: 0; display: grid; gap: 3px; }
.transition-route span, .transition-blockers__head span, .transition-blockers li span, .transition-blockers p { color: var(--text-secondary); font-size: var(--text-xs); }
.transition-route strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-sm); }
.transition-route__arrow { color: var(--color-brand-600) !important; font-size: var(--text-lg) !important; }
.transition-blockers { display: grid; gap: 8px; }
.transition-blockers__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.transition-blockers__head span { color: var(--color-warning-600); }
.transition-blockers ul { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.transition-blockers li { display: grid; gap: 2px; padding: 8px 10px; background: var(--color-warning-50); border-left: 3px solid var(--color-warning); border-radius: 4px; }
.transition-blockers li strong { font-size: var(--text-sm); font-weight: 500; }
.transition-blockers p { margin: 0; }
.transition-reason { display: grid; gap: 6px; color: var(--text-primary); font-size: var(--text-sm); }
.transition-modal__actions { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 520px) { .transition-route { grid-template-columns: minmax(0, 1fr); } .transition-route__arrow { transform: rotate(90deg); } .transition-modal__actions { flex-wrap: wrap; } }
</style>
