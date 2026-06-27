import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createAuditProject,
  deleteProjectAttachment,
  fetchAuditMeta,
  fetchAuditProject,
  fetchAuditProjectPage,
  fetchAuditProjects,
  fetchAuditSummary,
  fetchProjectAttachments,
  saveFieldOption,
  updateAuditProgress,
  updateAuditProject,
  uploadProjectAttachment,
} from '@/api/audit'
import type {
  AuditFieldConfig,
  AuditFieldOption,
  AuditFilters,
  AuditMeta,
  AuditProject,
  AuditProjectAttachment,
  AuditStageCode,
  AuditSummary,
} from '@/types/audit'

const DEFAULT_FILTERS: AuditFilters = {
  keyword: '',
  stage: '',
  priority: '',
  category: '',
  docStatus: '',
  status: '',
  owner: '',
  startDate: '',
  endDate: '',
  onlyOverdue: false,
  page: 1,
  pageSize: 10,
  sort: 'stage',
}

export const useAuditStore = defineStore('audit', () => {
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const projects = ref<AuditProject[]>([])
  const total = ref(0)
  const selectedProject = ref<AuditProject | null>(null)
  const filters = ref<AuditFilters>({ ...DEFAULT_FILTERS })
  const meta = ref<AuditMeta>({ stages: [], fieldConfigs: [], options: {} })
  const summary = ref<AuditSummary>({
    totalProjects: 0,
    inAuditProjects: 0,
    completedProjects: 0,
    overdueProjects: 0,
    totalSubmittedAmount: 0,
    totalFirstCutAmount: 0,
    totalSecondCutAmount: 0,
    monthlyNewProjects: 0,
    upcomingDueProjects: 0,
    stageCounts: {},
  })

  const cardFields = computed(() => meta.value.fieldConfigs.filter((f) => f.visibleInCard && f.enabled))
  const tableFields = computed(() => meta.value.fieldConfigs.filter((f) => f.visibleInTable && f.enabled))
  const detailFields = computed(() => meta.value.fieldConfigs.filter((f) => f.visibleInDetail && f.enabled))
  const formFields = computed(() => meta.value.fieldConfigs.filter((f) => f.visibleInForm && f.enabled))

  const projectsByStage = computed<Record<string, AuditProject[]>>(() => {
    const grouped: Record<string, AuditProject[]> = {}
    for (const stage of meta.value.stages) grouped[stage.code] = []
    for (const project of projects.value) {
      grouped[project.stage] ||= []
      grouped[project.stage].push(project)
    }
    return grouped
  })

  async function refreshAll() {
    loading.value = true
    error.value = null
    try {
      const [nextMeta, pageResult, nextSummary] = await Promise.all([
        fetchAuditMeta(),
        fetchAuditProjectPage(filters.value),
        fetchAuditSummary(),
      ])
      meta.value = nextMeta
      projects.value = pageResult.projects
      total.value = pageResult.total
      summary.value = nextSummary
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function refreshProjects() {
    loading.value = true
    error.value = null
    try {
      const [pageResult, nextSummary] = await Promise.all([
        fetchAuditProjectPage(filters.value),
        fetchAuditSummary(),
      ])
      projects.value = pageResult.projects
      total.value = pageResult.total
      summary.value = nextSummary
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function selectProject(project: AuditProject) {
    selectedProject.value = await fetchAuditProject(project.id)
  }

  async function refreshSelectedProjectAttachments() {
    if (!selectedProject.value) return
    selectedProject.value.attachments = await fetchProjectAttachments(selectedProject.value.id)
  }

  async function uploadAttachment(file: File): Promise<AuditProjectAttachment> {
    if (!selectedProject.value) throw new Error('请先选择项目')
    const attachment = await uploadProjectAttachment(selectedProject.value.id, file)
    selectedProject.value.attachments = [attachment, ...(selectedProject.value.attachments || [])]
    return attachment
  }

  async function removeAttachment(attachmentId: string) {
    await deleteProjectAttachment(attachmentId)
    if (selectedProject.value) {
      selectedProject.value.attachments = (selectedProject.value.attachments || []).filter((item) => item.id !== attachmentId)
    }
  }

  async function saveProject(project: Partial<AuditProject>) {
    saving.value = true
    try {
      if (project.id) {
        await updateAuditProject(project.id, project)
      } else {
        await createAuditProject(project)
      }
      await refreshProjects()
    } finally {
      saving.value = false
    }
  }

  async function moveProject(project: AuditProject, stageCode: AuditStageCode, operator: string) {
    saving.value = true
    try {
      const updated = await updateAuditProgress(project.id, { stageCode, operator, note: `流转至 ${stageCode}` })
      projects.value = projects.value.map((item) => (item.id === updated.id ? updated : item))
      if (selectedProject.value?.id === updated.id) selectedProject.value = updated
      await refreshProjects()
    } finally {
      saving.value = false
    }
  }

  async function addOption(groupKey: string, value: string): Promise<AuditFieldOption> {
    const option = await saveFieldOption({ groupKey, optionLabel: value, optionValue: value, enabled: true, sortOrder: 999 })
    meta.value.options[groupKey] ||= []
    meta.value.options[groupKey].push(option)
    return option
  }

  function readField(project: AuditProject, config: AuditFieldConfig): string | number | boolean {
    const path = config.bindField || config.fieldKey
    const parts = path.split('.')
    let current: unknown = project
    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = (current as Record<string, unknown>)[part]
      } else {
        current = project.customFields?.[config.fieldKey] ?? ''
        break
      }
    }
    return (current ?? '') as string | number | boolean
  }

  function resetFilters() {
    filters.value = { ...DEFAULT_FILTERS }
  }

  return {
    loading,
    saving,
    error,
    projects,
    total,
    selectedProject,
    filters,
    meta,
    summary,
    cardFields,
    tableFields,
    detailFields,
    formFields,
    projectsByStage,
    refreshAll,
    refreshProjects,
    selectProject,
    refreshSelectedProjectAttachments,
    uploadAttachment,
    removeAttachment,
    saveProject,
    moveProject,
    addOption,
    readField,
    resetFilters,
  }
})
