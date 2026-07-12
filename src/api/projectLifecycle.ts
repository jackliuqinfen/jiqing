import { getAuthToken } from '@/api/system'
import type {
  ProjectLifecycleErrorPayload,
  ProjectLifecycleSnapshot,
  ProjectLifecycleTransitionRequest,
  ProjectLifecycleTransitionResponse,
  ProjectLifecycleValidateRequest,
  ProjectLifecycleValidateResponse,
} from '@/types/projectLifecycle'

const API_BASE = import.meta.env.VITE_AUDIT_API_BASE || '/api'

export class ProjectLifecycleApiError extends Error {
  readonly status: number
  readonly payload: ProjectLifecycleErrorPayload
  readonly code?: string
  readonly blockers
  readonly currentVersion?: number

  constructor(status: number, payload: ProjectLifecycleErrorPayload) {
    super(payload.error || `请求失败: ${status || '网络异常'}`)
    this.name = 'ProjectLifecycleApiError'
    this.status = status
    this.payload = payload
    this.code = payload.code
    this.blockers = payload.blockers || []
    this.currentVersion = payload.currentVersion
  }
}

type ApiResult<T> = { success: boolean; data?: T; error?: string } & ProjectLifecycleErrorPayload

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken()
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers || {}),
      },
    })
  } catch {
    throw new ProjectLifecycleApiError(0, { error: '网络连接失败，请检查连接后重试。', code: 'network_error' })
  }

  let payload: ApiResult<T> = { success: false, error: `请求失败: ${response.status}` }
  try {
    payload = (await response.json()) as ApiResult<T>
  } catch {
    // Keep the HTTP status even when a proxy returns a non-JSON error page.
  }
  if (!response.ok || !payload.success || payload.data === undefined) {
    throw new ProjectLifecycleApiError(response.status, payload)
  }
  return payload.data
}

export function fetchProjectLifecycleSnapshot(projectId: string): Promise<ProjectLifecycleSnapshot> {
  return request(`/projects/${encodeURIComponent(projectId)}/lifecycle`)
}

export function validateProjectLifecycle(
  projectId: string,
  data: ProjectLifecycleValidateRequest = {},
): Promise<ProjectLifecycleValidateResponse> {
  return request(`/projects/${encodeURIComponent(projectId)}/lifecycle/validate`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function transitionProjectLifecycle(
  projectId: string,
  data: ProjectLifecycleTransitionRequest,
): Promise<ProjectLifecycleTransitionResponse> {
  return request(`/projects/${encodeURIComponent(projectId)}/lifecycle/transitions`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
