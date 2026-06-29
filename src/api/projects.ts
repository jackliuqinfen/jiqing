import { getAuthToken } from '@/api/system'
import type {
  ProjectFile,
  ProjectFilters,
  ProjectMeta,
  ProjectOperationLog,
  ProjectRecord,
  ProjectSettlement,
  ProjectSummary,
  ProjectVariation,
} from '@/types'
import type { ApiResult } from '@/types/audit'

const API_BASE = import.meta.env.VITE_AUDIT_API_BASE || '/api'

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

function buildQuery(filters?: Partial<ProjectFilters> & Record<string, unknown>) {
  const params = new URLSearchParams()
  if (!filters) return ''
  if (filters.keyword) params.set('keyword', String(filters.keyword))
  if (filters.projectStatus) params.set('projectStatus', String(filters.projectStatus))
  if (filters.settlementStatus) params.set('settlementStatus', String(filters.settlementStatus))
  if (filters.managerName) params.set('managerName', String(filters.managerName))
  if (filters.onlyMissingDocuments) params.set('onlyMissingDocuments', '1')
  if (filters.sort) params.set('sort', String(filters.sort))
  if (filters.page) params.set('page', String(filters.page))
  if (filters.pageSize) params.set('pageSize', String(filters.pageSize))
  return params.toString() ? `?${params.toString()}` : ''
}

export function fetchProjectMeta(): Promise<ProjectMeta> {
  return request('/projects/meta')
}

export function fetchProjectSummary(): Promise<ProjectSummary> {
  return request('/projects/summary')
}

export function fetchProjectRecords(filters?: Partial<ProjectFilters>): Promise<{ data: ProjectRecord[]; total: number; page: number; pageSize: number }> {
  const token = getAuthToken()
  return fetch(`${API_BASE}/projects${buildQuery(filters)}`, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then(async (res) => {
    const payload = (await res.json()) as ApiResult<ProjectRecord[]>
    if (!res.ok || !payload.success) throw new Error(payload.error || `请求失败: ${res.status}`)
    return {
      data: payload.data,
      total: Number(payload.meta?.total || payload.data.length),
      page: Number(payload.meta?.page || filters?.page || 1),
      pageSize: Number(payload.meta?.pageSize || filters?.pageSize || 20),
    }
  })
}

export function fetchProjectRecord(id: string): Promise<ProjectRecord> {
  return request(`/projects/${id}`)
}

export function createProjectRecord(data: Partial<ProjectRecord>): Promise<ProjectRecord> {
  return request('/projects', { method: 'POST', body: JSON.stringify(data) })
}

export function updateProjectRecord(id: string, data: Partial<ProjectRecord>): Promise<ProjectRecord> {
  return request(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deleteProjectRecord(id: string): Promise<null> {
  return request(`/projects/${id}`, { method: 'DELETE' })
}

export function fetchProjectFiles(params?: { projectId?: string; keyword?: string; categoryKey?: string }): Promise<ProjectFile[]> {
  const query = new URLSearchParams()
  if (params?.projectId) query.set('projectId', params.projectId)
  if (params?.keyword) query.set('keyword', params.keyword)
  if (params?.categoryKey) query.set('categoryKey', params.categoryKey)
  return request(`/project-files${query.toString() ? `?${query.toString()}` : ''}`)
}

export function fetchProjectFilePreviewBlob(id: string): Promise<Blob> {
  return authorizedBlob(`/project-files/${id}/preview`)
}

export function fetchProjectFileDownloadBlob(id: string): Promise<Blob> {
  return authorizedBlob(`/project-files/${id}/download`)
}

function authorizedBlob(path: string): Promise<Blob> {
  const token = getAuthToken()
  return fetch(`${API_BASE}${path}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  }).then(async (res) => {
    if (!res.ok) {
      let message = `请求失败: ${res.status}`
      try {
        const payload = await res.json()
        message = payload.error || message
      } catch {
        // ignore
      }
      throw new Error(message)
    }
    return res.blob()
  })
}

export async function uploadProjectFile(projectId: string, payload: { categoryKey: string; displayName: string; file: File }): Promise<ProjectFile> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('categoryKey', payload.categoryKey)
  form.append('displayName', payload.displayName)
  form.append('file', payload.file)
  const res = await fetch(`${API_BASE}/projects/${projectId}/files`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: form,
  })
  const payloadJson = (await res.json()) as ApiResult<ProjectFile>
  if (!res.ok || !payloadJson.success) throw new Error(payloadJson.error || `请求失败: ${res.status}`)
  return payloadJson.data
}

export function renameProjectFile(id: string, displayName: string): Promise<ProjectFile> {
  return request(`/project-files/${id}`, { method: 'PUT', body: JSON.stringify({ displayName }) })
}

export function deleteProjectFile(id: string): Promise<null> {
  return request(`/project-files/${id}`, { method: 'DELETE' })
}

export function fetchProjectSettlements(projectId?: string): Promise<ProjectSettlement[]> {
  const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : ''
  return request(`/project-settlements${query}`)
}

export function fetchProjectSettlement(id: string): Promise<ProjectSettlement> {
  return request(`/project-settlements/${id}`)
}

export function saveProjectSettlement(projectId: string, data: Partial<ProjectSettlement>): Promise<ProjectSettlement> {
  return request(`/projects/${projectId}/settlements`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateProjectSettlement(id: string, data: Partial<ProjectSettlement>): Promise<ProjectSettlement> {
  return request(`/project-settlements/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function fetchProjectVariations(projectId?: string): Promise<ProjectVariation[]> {
  const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : ''
  return request(`/project-variations${query}`)
}

export function saveProjectVariation(projectId: string, data: Partial<ProjectVariation>): Promise<ProjectVariation> {
  return request(`/projects/${projectId}/variations`, { method: 'POST', body: JSON.stringify(data) })
}

export function updateProjectVariation(id: string, data: Partial<ProjectVariation>): Promise<ProjectVariation> {
  return request(`/project-variations/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function fetchProjectLogs(projectId: string): Promise<ProjectOperationLog[]> {
  return request(`/projects/${projectId}`).then((item) => (item as ProjectRecord).logs || [])
}
