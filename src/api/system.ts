import type {
  AdminStats,
  AdminUser,
  AuthSession,
  CreateAdminUserDto,
  CurrentTheme,
  OperationLogEntry,
  SystemSetting,
  SystemSettingKey,
  SystemSettingValue,
  ThemeOption,
  ThemeSetting,
  UpdateAdminUserDto,
  UserProfile,
} from '@/types'
import type { ApiResult } from '@/types/audit'

const API_BASE = import.meta.env.VITE_AUDIT_API_BASE || '/api'
const AUTH_TOKEN_KEY = '__jiqing_auth_token__'
const AUTH_EXPIRES_KEY = '__jiqing_auth_expires__'

export function getAuthToken(): string {
  return localStorage.getItem(AUTH_TOKEN_KEY) || ''
}

function setAuthSession(token: string, expiresAt: number) {
  localStorage.setItem(AUTH_TOKEN_KEY, token)
  localStorage.setItem(AUTH_EXPIRES_KEY, String(expiresAt))
}

export function clearAuthSession() {
  localStorage.removeItem(AUTH_TOKEN_KEY)
  localStorage.removeItem(AUTH_EXPIRES_KEY)
}

function normalizeUser(user: UserProfile & { isActive?: boolean }): UserProfile {
  return {
    id: user.id,
    username: user.username,
    displayName: user.displayName,
    email: user.email || '',
    role: user.role,
    createdAt: user.createdAt,
  }
}

function normalizeAdminUser(user: AdminUser & { isActive?: boolean }): AdminUser {
  return {
    id: user.id,
    userId: user.userId || user.id,
    username: user.username,
    displayName: user.displayName,
    email: user.email || '',
    role: user.role,
    isActive: user.isActive !== false,
    createdAt: user.createdAt,
    updatedAt: user.updatedAt,
  }
}

type RawOperationLog = {
  id: string
  user_id?: string
  username?: string
  role?: OperationLogEntry['role']
  action: string
  target_type?: string
  target_id?: string
  result?: string
  ip_address?: string
  user_agent?: string
  detail_json?: string
  created_at?: string
}

function normalizeOperationLog(row: RawOperationLog): OperationLogEntry {
  let detail: Record<string, unknown> = {}
  if (row.detail_json) {
    try {
      detail = JSON.parse(row.detail_json) as Record<string, unknown>
    } catch {
      detail = { raw: row.detail_json }
    }
  }
  return {
    id: row.id,
    userId: row.user_id || '',
    username: row.username || '系统',
    role: row.role || '',
    action: row.action,
    targetType: row.target_type || '',
    targetId: row.target_id || '',
    result: row.result || 'success',
    ipAddress: row.ip_address || '',
    userAgent: row.user_agent || '',
    detail,
    createdAt: row.created_at || '',
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

export async function loginWithPassword(username: string, password: string): Promise<AuthSession> {
  const data = await request<{ token: string; expiresAt: number; user: UserProfile }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setAuthSession(data.token, data.expiresAt)
  return {
    accessToken: data.token,
    refreshToken: '',
    expiresAt: data.expiresAt,
    user: normalizeUser(data.user),
  }
}

export async function getCurrentSession(): Promise<AuthSession | null> {
  const token = getAuthToken()
  const expiresAt = Number(localStorage.getItem(AUTH_EXPIRES_KEY) || '0')
  if (!token || expiresAt * 1000 < Date.now()) {
    clearAuthSession()
    return null
  }
  const user = await request<UserProfile>('/auth/me')
  return { accessToken: token, refreshToken: '', expiresAt, user: normalizeUser(user) }
}

export async function logoutSession(): Promise<void> {
  try {
    await request<null>('/auth/logout', { method: 'POST', body: '{}' })
  } finally {
    clearAuthSession()
  }
}

export async function getAdminUsers(): Promise<AdminUser[]> {
  const users = await request<AdminUser[]>('/admin/users')
  return users.map(normalizeAdminUser)
}

export async function signUpWithProfile(dto: CreateAdminUserDto): Promise<void> {
  await request<AdminUser[]>('/admin/users', { method: 'POST', body: JSON.stringify(dto) })
}

export async function updateAdminUser(dto: UpdateAdminUserDto): Promise<void> {
  await request<AdminUser>(`/admin/users/${dto.id}`, { method: 'PUT', body: JSON.stringify(dto) })
}

export async function getAdminStats(): Promise<AdminStats> {
  return request<AdminStats>('/admin/stats')
}

export async function getOperationLogs(): Promise<OperationLogEntry[]> {
  const rows = await request<RawOperationLog[]>('/admin/operation-logs')
  return rows.map(normalizeOperationLog)
}

export async function getAllSystemSettings(): Promise<SystemSetting[]> {
  return request<SystemSetting[]>('/system/settings')
}

export async function getSystemSetting(key: SystemSettingKey): Promise<SystemSetting | null> {
  const settings = await getAllSystemSettings()
  return settings.find((item) => item.key === key) || null
}

export async function setSystemSetting(
  key: SystemSettingKey,
  value: SystemSettingValue,
  _updatedBy: string
): Promise<void> {
  await request<null>(`/system/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) })
}

export async function getThemeOptions(): Promise<ThemeOption[]> {
  return request<ThemeOption[]>('/system/theme/options')
}

export async function getCurrentTheme(): Promise<CurrentTheme> {
  return request<CurrentTheme>('/system/theme/current')
}

export async function updateCurrentTheme(setting: ThemeSetting): Promise<CurrentTheme> {
  return request<CurrentTheme>('/system/theme/current', { method: 'PUT', body: JSON.stringify(setting) })
}

export async function resetCurrentTheme(): Promise<CurrentTheme> {
  return request<CurrentTheme>('/system/theme/reset', { method: 'POST', body: '{}' })
}
