import type {
  ApiResult,
  AuditFieldConfig,
  AuditFieldOption,
  AuditFilters,
  AuditDashboardOverview,
  AuditMeta,
  AuditProject,
  AuditProjectAttachment,
  AuditSummary,
} from '@/types/audit'
import { getAuthToken } from '@/api/system'

const API_BASE = import.meta.env.VITE_AUDIT_API_BASE || '/api'
const FORBIDDEN_ATTACHMENT_SUFFIXES = ['.zip', '.rar', '.7z', '.tar', '.tar.gz', '.tgz', '.gz', '.bz2', '.xz', '.iso']

function buildQuery(filters?: Partial<AuditFilters>): string {
  const params = new URLSearchParams()
  if (!filters) return ''
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.stage) params.set('stage', filters.stage)
  if (filters.priority) params.set('priority', filters.priority)
  if (filters.category) params.set('category', filters.category)
  if (filters.docStatus) params.set('doc_status', filters.docStatus)
  if (filters.status) params.set('status', filters.status)
  if (filters.owner) params.set('owner', filters.owner)
  if (filters.startDate) params.set('startDate', filters.startDate)
  if (filters.endDate) params.set('endDate', filters.endDate)
  if (filters.onlyOverdue) params.set('only_overdue', '1')
  if (filters.page) params.set('page', String(filters.page))
  if (filters.pageSize) params.set('pageSize', String(filters.pageSize))
  if (filters.sort) params.set('sort', filters.sort)
  const text = params.toString()
  return text ? `?${text}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  })
  const payload = (await res.json()) as ApiResult<T>
  if (!res.ok || !payload.success) {
    throw new Error(payload.error || `请求失败: ${res.status}`)
  }
  return payload.data
}

async function authorizedBlob(path: string): Promise<Blob> {
  const token = getAuthToken()
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  if (!res.ok) {
    let message = `请求失败: ${res.status}`
    try {
      const payload = await res.json()
      message = payload.error || message
    } catch {
      // Binary endpoints only return JSON on errors.
    }
    throw new Error(message)
  }
  return res.blob()
}

export function fetchAuditMeta(): Promise<AuditMeta> {
  return request('/audit/admin/meta')
}

export function fetchAuditProjects(filters?: Partial<AuditFilters>): Promise<AuditProject[]> {
  return request(`/audit/projects${buildQuery(filters)}`)
}

export async function fetchAuditProjectPage(filters?: Partial<AuditFilters>): Promise<{ projects: AuditProject[]; total: number; page: number; pageSize: number }> {
  const token = getAuthToken()
  const res = await fetch(`${API_BASE}/audit/projects${buildQuery(filters)}`, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  const payload = (await res.json()) as ApiResult<AuditProject[]>
  if (!res.ok || !payload.success) {
    throw new Error(payload.error || `请求失败: ${res.status}`)
  }
  return {
    projects: payload.data,
    total: Number(payload.meta?.total || payload.data.length),
    page: Number(payload.meta?.page || filters?.page || 1),
    pageSize: Number(payload.meta?.pageSize || filters?.pageSize || 50),
  }
}

export function fetchAuditProject(id: string): Promise<AuditProject> {
  return request(`/audit/projects/${id}`)
}

export function fetchProjectAttachments(projectId: string): Promise<AuditProjectAttachment[]> {
  return request(`/audit/projects/${projectId}/attachments`)
}

export function validateAttachmentFile(file: File): string {
  const name = file.name.toLowerCase()
  const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath
  if (relativePath && relativePath.includes('/')) return '不支持上传文件夹'
  if (FORBIDDEN_ATTACHMENT_SUFFIXES.some((suffix) => name.endsWith(suffix))) return '不允许上传压缩包或镜像类文件'
  return ''
}

export async function uploadProjectAttachment(projectId: string, file: File): Promise<AuditProjectAttachment> {
  const message = validateAttachmentFile(file)
  if (message) throw new Error(message)
  const token = getAuthToken()
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/audit/projects/${projectId}/attachments`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: form,
  })
  const payload = (await res.json()) as ApiResult<AuditProjectAttachment>
  if (!res.ok || !payload.success) throw new Error(payload.error || `请求失败: ${res.status}`)
  return payload.data
}

export function fetchAttachmentPreviewBlob(id: string): Promise<Blob> {
  return authorizedBlob(`/audit/attachments/${id}/preview`)
}

export function fetchAttachmentDownloadBlob(id: string): Promise<Blob> {
  return authorizedBlob(`/audit/attachments/${id}/download`)
}

export function deleteProjectAttachment(id: string): Promise<null> {
  return request(`/audit/attachments/${id}`, { method: 'DELETE' })
}

export function createAuditProject(data: Partial<AuditProject>): Promise<AuditProject> {
  return request('/audit/projects', { method: 'POST', body: JSON.stringify(data) })
}

export function updateAuditProject(id: string, data: Partial<AuditProject>): Promise<AuditProject> {
  return request(`/audit/projects/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function updateAuditProgress(id: string, body: { stageCode: string; operator: string; note?: string }): Promise<AuditProject> {
  return request(`/audit/projects/${id}/progress`, { method: 'POST', body: JSON.stringify(body) })
}

export function fetchAuditSummary(): Promise<AuditSummary> {
  return request('/audit/dashboard/summary')
}

export function fetchAuditDashboardOverview(): Promise<AuditDashboardOverview> {
  return request('/audit/dashboard/overview')
}

export function fetchFieldConfigs(): Promise<AuditFieldConfig[]> {
  return request('/audit/admin/field-configs')
}

export function saveFieldConfig(data: Partial<AuditFieldConfig>): Promise<AuditFieldConfig> {
  const method = data.id ? 'PUT' : 'POST'
  const path = data.id ? `/audit/admin/field-configs/${data.id}` : '/audit/admin/field-configs'
  return request(path, { method, body: JSON.stringify(data) })
}

export function fetchFieldOptions(groupKey?: string): Promise<AuditFieldOption[]> {
  const query = groupKey ? `?group_key=${encodeURIComponent(groupKey)}` : ''
  return request(`/audit/admin/field-options${query}`)
}

export function saveFieldOption(data: Partial<AuditFieldOption>): Promise<AuditFieldOption> {
  const method = data.id ? 'PUT' : 'POST'
  const path = data.id ? `/audit/admin/field-options/${data.id}` : '/audit/admin/field-options'
  return request(path, { method, body: JSON.stringify(data) })
}

export function deleteFieldConfig(id: string): Promise<null> {
  return request(`/audit/admin/field-configs/${id}`, { method: 'DELETE' })
}

export function deleteFieldOption(id: string): Promise<null> {
  return request(`/audit/admin/field-options/${id}`, { method: 'DELETE' })
}
