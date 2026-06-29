export type AuditViewMode = 'kanban' | 'gantt' | 'table'
export type AuditLayoutMode = 'horizontal' | 'vertical' | 'compact' | 'standard' | 'bigscreen'
export type AuditStageCode = 'submitted' | 'first_audit' | 'second_audit' | 'conclusion' | 'archived'

export interface AuditStageMeta {
  code: AuditStageCode
  title: string
  color: string
}

export interface AuditFieldOption {
  id: string
  groupKey: string
  fieldKey?: string
  optionLabel: string
  optionValue: string
  color: string
  sortOrder: number
  enabled: boolean
}

export interface AuditFieldConfig {
  id: string
  entityType: 'project' | 'stage' | string
  fieldKey: string
  fieldLabel: string
  fieldName?: string
  fieldType: 'text' | 'textarea' | 'number' | 'date' | 'select' | 'boolean' | string
  module?: string
  displayScene?: string
  stageKey?: string
  optionGroup: string
  bindField: string
  required: boolean
  visibleInCard: boolean
  visibleInTable: boolean
  visibleInDetail: boolean
  visibleInForm: boolean
  visibleInGantt: boolean
  placeholder?: string
  defaultValue?: string
  sortOrder: number
  enabled: boolean
}

export interface AuditProject {
  id: string
  projectId: string
  projectCode: string
  projectName: string
  auditedUnit: string
  auditType: string
  sectionBuilding: string
  settlementNo: string
  category: string
  priority: string
  contractor: { name: string; phone?: string }
  firstAudit: { companyName: string; auditor: { name: string } }
  secondAudit: { department: string; auditor: { name: string } }
  amount: {
    contractAmount: number
    submittedAmount: number
    firstAuditAmount: number
    secondAuditAmount: number
    auditDifference: number
    finalPayable: number
    paidAmount: number
  }
  deadline: { submitDate: string; auditDeadline: string }
  startDate: string
  plannedEndDate: string
  actualEndDate: string
  docStatus: string
  stage: AuditStageCode
  status: string
  progressPercent: number
  managerName: string
  isDelayed: boolean
  delayDays: number
  description: string
  remark: { dispute: string; coordination: string }
  sortOrder: number
  isArchived: boolean
  createdAt: string
  updatedAt: string
  customFields: Record<string, string>
  logs?: AuditProjectLog[]
  stages?: AuditProjectStage[]
  attachments?: AuditProjectAttachment[]
}

export interface AuditProjectLog {
  id: string
  project_id: string
  action: string
  operator: string
  note: string
  created_at: string
}

export interface AuditProjectStage {
  id: string
  project_id: string
  stage_code: string
  stage_name: string
  stage_order: number
  start_date: string
  end_date: string
  owner: string
  handler_name: string
  status: string
  progress_percent: number
  remark: string
  entered_at: string
  finished_at: string
}

export interface AuditProjectAttachment {
  id: string
  projectId: string
  projectName?: string
  projectCode?: string
  managerName?: string
  originalName: string
  storedName: string
  fileExt: string
  mimeType: string
  fileSize: number
  uploadedBy: string
  uploadedByName: string
  createdAt: string
  previewUrl: string
  downloadUrl: string
  canPreview: boolean
  project_id?: string
  file_name?: string
  file_url?: string
  file_type?: string
  uploaded_by?: string
  uploaded_at?: string
}

export interface AttachmentLibraryFilters {
  keyword?: string
  fileType?: string
}

export interface AuditSummary {
  totalProjects: number
  inAuditProjects: number
  completedProjects: number
  overdueProjects: number
  totalSubmittedAmount: number
  totalFirstCutAmount: number
  totalSecondCutAmount: number
  monthlyNewProjects: number
  upcomingDueProjects: number
  stageCounts: Record<string, number>
}

export interface AuditDashboardOverview {
  summary: AuditSummary
  statusDistribution: { type: string; value: number }[]
  stageDistribution: { stage: string; stageCode: string; count: number }[]
  trendData: { month: string; type: string; count: number }[]
  cardSparklines: Record<string, number[]>
  riskQueue: {
    id: string
    projectName: string
    managerName: string
    auditDeadline: string
    isDelayed: boolean
    delayDays: number
  }[]
  amountTop: { id: string; name: string; amount: number }[]
}

export interface AuditMeta {
  stages: AuditStageMeta[]
  fieldConfigs: AuditFieldConfig[]
  options: Record<string, AuditFieldOption[]>
}

export interface AuditFilters {
  keyword: string
  stage: string
  priority: string
  category: string
  docStatus: string
  status: string
  owner: string
  startDate: string
  endDate: string
  onlyOverdue: boolean
  page: number
  pageSize: number
  sort: string
}

export interface ApiResult<T> {
  success: boolean
  data: T
  error?: string
  meta?: { total?: number; page?: number; pageSize?: number; [key: string]: unknown }
}
