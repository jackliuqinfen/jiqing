import type {
  ApiResult,
  AuditFieldConfig,
  AuditFieldOption,
  AuditFilters,
  AuditMeta,
  AuditProject,
  AuditSummary,
} from '@/types/audit'

const API_BASE = import.meta.env.VITE_AUDIT_API_BASE || '/api'

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
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  const payload = (await res.json()) as ApiResult<T>
  if (!res.ok || !payload.success) {
    throw new Error(payload.error || `请求失败: ${res.status}`)
  }
  return payload.data
}

export function fetchAuditMeta(): Promise<AuditMeta> {
  return request('/audit/admin/meta')
}

export function fetchAuditProjects(filters?: Partial<AuditFilters>): Promise<AuditProject[]> {
  return request(`/audit/projects${buildQuery(filters)}`)
}

export async function fetchAuditProjectPage(filters?: Partial<AuditFilters>): Promise<{ projects: AuditProject[]; total: number; page: number; pageSize: number }> {
  const res = await fetch(`${API_BASE}/audit/projects${buildQuery(filters)}`, {
    headers: { 'Content-Type': 'application/json' },
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
