import { onScopeDispose, ref } from 'vue'
import {
  createProjectIntakeDraft,
  DocumentReviewApiError,
  listProjectIntakeDrafts,
  saveProjectIntakeDraft,
} from '@/api/documentReview'
import type {
  ContractDraftValues,
  ManualProjectIntakeUiState,
  ManualProjectValues,
  ProjectIntakeDraft,
} from '@/types/documentReview'

const AUTOSAVE_DELAY_MS = 800
const CONFLICT_MESSAGE = '草稿已在其他窗口更新，请重新载入后继续。'

export interface ManualProjectIntakeDraftSnapshot {
  values: ContractDraftValues
  projectValues: ManualProjectValues
  uiState: ManualProjectIntakeUiState
  documentId: string
  documentVersionId: string
}

interface ManualProjectIntakeDraftOptions {
  snapshot: () => ManualProjectIntakeDraftSnapshot
  restore: (snapshot: ManualProjectIntakeDraftSnapshot) => void
  onError: (message: string) => void
}

export function useManualProjectIntakeDraft(options: ManualProjectIntakeDraftOptions) {
  const drafts = ref<ProjectIntakeDraft[]>([])
  const activeDraft = ref<ProjectIntakeDraft | null>(null)
  const loadingDrafts = ref(false)
  const savingDraft = ref(false)

  let saveTimer: ReturnType<typeof setTimeout> | null = null
  let saveTail: Promise<ProjectIntakeDraft | null> = Promise.resolve(null)
  let pendingSaveCount = 0
  let autosaveStopped = false
  let activeGeneration = 0

  function unfinished(items: ProjectIntakeDraft[]) {
    return items
      .filter((draft) => draft.status === 'draft' || draft.status === 'document_attached')
      .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
  }

  function replaceDraft(next: ProjectIntakeDraft) {
    activeDraft.value = next
    drafts.value = unfinished([next, ...drafts.value.filter((item) => item.id !== next.id)])
    return next
  }

  function draftSnapshot(draft: ProjectIntakeDraft): ManualProjectIntakeDraftSnapshot {
    return {
      values: { ...draft.values },
      projectValues: { ...draft.projectValues },
      uiState: { ...draft.uiState },
      documentId: draft.documentId || '',
      documentVersionId: draft.documentVersionId || '',
    }
  }

  function handleMutationError(error: unknown) {
    if (error instanceof DocumentReviewApiError && error.status === 409) {
      autosaveStopped = true
      if (saveTimer) clearTimeout(saveTimer)
      saveTimer = null
      options.onError(CONFLICT_MESSAGE)
      return
    }
    options.onError(error instanceof Error ? error.message : '项目草稿保存失败，请稍后重试。')
  }

  async function loadDrafts() {
    loadingDrafts.value = true
    try {
      drafts.value = unfinished(await listProjectIntakeDrafts())
      return drafts.value
    } catch (error) {
      options.onError(error instanceof Error ? error.message : '项目草稿加载失败，请稍后重试。')
      return []
    } finally {
      loadingDrafts.value = false
    }
  }

  function resumeDraft(draft: ProjectIntakeDraft) {
    clearScheduledSave()
    activeGeneration += 1
    autosaveStopped = false
    activeDraft.value = draft
    options.restore(draftSnapshot(draft))
    return draft
  }

  async function persistSnapshot() {
    if (autosaveStopped) return activeDraft.value
    const generation = activeGeneration
    const snapshot = options.snapshot()
    const active = activeDraft.value
    try {
      const saved = active
        ? await saveProjectIntakeDraft(active.id, {
            expectedRevision: active.revision,
            values: snapshot.values,
            projectValues: snapshot.projectValues,
            uiState: snapshot.uiState,
            documentId: snapshot.documentId || undefined,
            documentVersionId: snapshot.documentVersionId || undefined,
          })
        : await createProjectIntakeDraft({
            values: snapshot.values,
            projectValues: snapshot.projectValues,
            uiState: snapshot.uiState,
            fallbackReason: 'manual_selected',
            fallbackNote: '手工创建项目并对照合同原文',
            documentId: snapshot.documentId || undefined,
            documentVersionId: snapshot.documentVersionId || undefined,
          })
      if (generation !== activeGeneration) return activeDraft.value
      if (active && activeDraft.value?.id !== active.id) return activeDraft.value
      return replaceDraft(saved)
    } catch (error) {
      handleMutationError(error)
      return activeDraft.value
    }
  }

  async function flushSave(): Promise<ProjectIntakeDraft | null> {
    clearScheduledSave()
    if (autosaveStopped) return activeDraft.value
    pendingSaveCount += 1
    savingDraft.value = true
    const request = saveTail.then(() => (
      autosaveStopped ? activeDraft.value : persistSnapshot()
    ))
    saveTail = request
    try {
      return await request
    } finally {
      pendingSaveCount = Math.max(0, pendingSaveCount - 1)
      savingDraft.value = pendingSaveCount > 0
    }
  }

  function scheduleSave() {
    if (autosaveStopped) return
    clearScheduledSave()
    saveTimer = setTimeout(() => {
      saveTimer = null
      void flushSave()
    }, AUTOSAVE_DELAY_MS)
  }

  async function attachDocument(documentId: string, documentVersionId: string) {
    clearScheduledSave()
    if (autosaveStopped) return activeDraft.value
    const current = options.snapshot()
    if (current.documentId !== documentId || current.documentVersionId !== documentVersionId) {
      options.onError('合同文件状态尚未同步，请重新选择 PDF。')
      return activeDraft.value
    }
    return flushSave()
  }

  function completeAndReset() {
    clearScheduledSave()
    activeGeneration += 1
    autosaveStopped = false
    const completedId = activeDraft.value?.id
    activeDraft.value = null
    if (completedId) drafts.value = drafts.value.filter((draft) => draft.id !== completedId)
  }

  function clearScheduledSave() {
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = null
  }

  onScopeDispose(clearScheduledSave)

  return {
    drafts,
    activeDraft,
    loadingDrafts,
    savingDraft,
    loadDrafts,
    resumeDraft,
    scheduleSave,
    flushSave,
    attachDocument,
    completeAndReset,
  }
}
