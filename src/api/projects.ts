import { getAuthToken } from '@/api/system'
import type {
  ProjectFile,
  ProjectFilters,
  ProjectEvidenceFile,
  ProjectMeta,
  ProjectOperationLog,
  ProjectRecord,
  ProjectSettlement,
  ProjectSummary,
  ProjectVariation,
  WorkItem,
} from '@/types'
import type { AuditProject } from '@/types/audit'
import type { ApiResult } from '@/types/audit'
import type { ProjectLifecycleBlocker, ProjectLifecycleStage } from '@/types/projectLifecycle'

const API_BASE = import.meta.env.VITE_AUDIT_API_BASE || '/api'

export type ProjectAuditStartErrorPayload = {
  error?: string
  code?: string
  blockers?: ProjectLifecycleBlocker[]
  currentStage?: ProjectLifecycleStage
  currentVersion?: number
  expectedVersion?: number
  lifecycleVersion?: number
  [key: string]: unknown
}

type ProjectAuditStartResult = { success: boolean; data?: AuditProject } & ProjectAuditStartErrorPayload

export class ProjectAuditStartApiError extends Error {
  readonly status: number
  readonly payload: ProjectAuditStartErrorPayload
  readonly code?: string
  readonly blockers: ProjectLifecycleBlocker[]
  readonly currentStage?: ProjectLifecycleStage
  readonly currentVersion?: number
  readonly expectedVersion?: number
  readonly lifecycleVersion?: number

  constructor(status: number, payload: ProjectAuditStartErrorPayload) {
    super(payload.error || `请求失败: ${status || '网络异常'}`)
    this.name = 'ProjectAuditStartApiError'
    this.status = status
    this.payload = payload
    this.code = payload.code
    this.blockers = payload.blockers || []
    this.currentStage = payload.currentStage
    this.currentVersion = payload.currentVersion
    this.expectedVersion = payload.expectedVersion
    this.lifecycleVersion = payload.lifecycleVersion
  }
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

function buildQuery(filters?: Partial<ProjectFilters> & Record<string, unknown>) {
  const params = new URLSearchParams()
  if (!filters) return ''
  if (filters.keyword) params.set('keyword', String(filters.keyword))
  if (filters.projectStatus) params.set('projectStatus', String(filters.projectStatus))
  if (filters.settlementStatus) params.set('settlementStatus', String(filters.settlementStatus))
  if (filters.managerName) params.set('managerName', String(filters.managerName))
  if (filters.onlyMissingDocuments) params.set('onlyMissingDocuments', '1')
  if (filters.onlyAuditLinked) params.set('onlyAuditLinked', '1')
  if (filters.onlyRisk) params.set('onlyRisk', '1')
  if (filters.onlyUpcomingDue) params.set('onlyUpcomingDue', '1')
  if (filters.onlyMonthlyNew) params.set('onlyMonthlyNew', '1')
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

export function fetchWorkItems(limit = 80): Promise<WorkItem[]> {
  return request(`/work-items?limit=${encodeURIComponent(String(limit))}`)
}

export function fetchProjectEvidence(params?: { keyword?: string; fileType?: string; stage?: string; uploader?: string }): Promise<ProjectEvidenceFile[]> {
  const query = new URLSearchParams()
  if (params?.keyword) query.set('keyword', params.keyword)
  if (params?.fileType) query.set('fileType', params.fileType)
  if (params?.stage) query.set('stage', params.stage)
  if (params?.uploader) query.set('uploader', params.uploader)
  return request(`/project-evidence${query.toString() ? `?${query.toString()}` : ''}`)
}

export async function startProjectAudit(projectId: string): Promise<AuditProject> {
  const token = getAuthToken()
  let response: Response
  try {
    response = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/start-audit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({}),
    })
  } catch {
    throw new ProjectAuditStartApiError(0, { error: '网络连接失败，请检查连接后重试。', code: 'network_error' })
  }

  let payload: ProjectAuditStartResult = { success: false, error: `请求失败: ${response.status}` }
  try {
    payload = (await response.json()) as ProjectAuditStartResult
  } catch {
    // Keep the HTTP status when an upstream proxy returns a non-JSON error page.
  }
  if (!response.ok || !payload.success || payload.data === undefined) {
    throw new ProjectAuditStartApiError(response.status, payload)
  }
  return payload.data
}

export function fetchProjectRecord(id: string): Promise<ProjectRecord> {
  return request(`/projects/${id}`)
}

export function createProjectDictionaryOption(groupKey: string, label: string): Promise<{ label: string; value: string }> {
  return request('/projects/dictionary-options', { method: 'POST', body: JSON.stringify({ groupKey, label }) })
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

export function updateProjectDocumentCategory(categoryKey: string, data: { required: boolean; requiredFromStage?: string }): Promise<ProjectMeta['categories'][number]> {
  return request(`/project-document-categories/${encodeURIComponent(categoryKey)}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function fetchProjectFilePreviewBlob(id: string): Promise<Blob> {
  return authorizedBlob(`/project-files/${id}/preview`)
}

export function fetchProjectFileDownloadBlob(id: string): Promise<Blob> {
  return authorizedBlob(`/project-files/${id}/download`)
}

export function fetchProjectFilesArchiveBlob(projectId: string): Promise<Blob> {
  return authorizedBlob(`/projects/${encodeURIComponent(projectId)}/files/archive`)
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

export async function uploadProjectFile(
  projectId: string,
  payload: { categoryKey: string; displayName: string; file: File },
  onProgress?: (percent: number) => void
): Promise<ProjectFile> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('categoryKey', payload.categoryKey)
  form.append('displayName', payload.displayName)
  form.append('file', payload.file)
  if (!onProgress) {
    const res = await fetch(`${API_BASE}/projects/${projectId}/files`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: form,
    })
    if (res.status === 413) {
      throw new Error('文件超过上传大小限制')
    }
    let payloadJson: ApiResult<ProjectFile>
    try {
      payloadJson = (await res.json()) as ApiResult<ProjectFile>
    } catch {
      throw new Error(`请求失败: ${res.status}`)
    }
    if (!res.ok || !payloadJson.success) throw new Error(payloadJson.error || `请求失败: ${res.status}`)
    return payloadJson.data
  }
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/projects/${projectId}/files`)
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return
      onProgress(Math.min(98, Math.round((event.loaded / event.total) * 100)))
    }
    xhr.onerror = () => reject(new Error('网络异常，资料上传失败'))
    xhr.onload = () => {
      if (xhr.status === 413) {
        reject(new Error('文件超过上传大小限制'))
        return
      }
      try {
        const payloadJson = JSON.parse(xhr.responseText || '{}') as ApiResult<ProjectFile>
        if (xhr.status < 200 || xhr.status >= 300 || !payloadJson.success) {
          reject(new Error(payloadJson.error || `请求失败: ${xhr.status}`))
          return
        }
        onProgress(100)
        resolve(payloadJson.data)
      } catch {
        reject(new Error(`请求失败: ${xhr.status || '未知'}`))
      }
    }
    xhr.send(form)
  })
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
