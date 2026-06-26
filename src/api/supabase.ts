import { createClient, SupabaseClient } from '@supabase/supabase-js'
import type {
  CostAuditItem,
  UserProfile,
  AuthSession,
  AdminUser,
  AdminRole,
  SystemSetting,
  SystemSettingKey,
  SystemSettingValue,
  CreateAdminUserDto,
  UpdateAdminUserDto,
  AdminStats,
} from '@/types'

// Supabase 连接配置 — 部署时替换为你自己的 Supabase 项目 URL 和 anon key
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://your-project-id.supabase.co'
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'your-anon-key-here'

export function isSupabaseConfigured(): boolean {
  return (
    !SUPABASE_URL.includes('your-project-id') &&
    SUPABASE_ANON_KEY !== 'your-anon-key-here'
  )
}

/** 表名常量 */
export const TABLE_NAME = 'cost_audit_items'
export const USER_PROFILES_TABLE = 'user_profiles'
export const SYSTEM_SETTINGS_TABLE = 'system_settings'

let supabaseInstance: SupabaseClient | null = null

/**
 * 获取 Supabase 客户端实例（单例）
 * 启用 auth session 持久化（localStorage），支持用户登录状态保持
 */
export function getSupabaseClient(): SupabaseClient {
  if (!supabaseInstance) {
    supabaseInstance = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        storageKey: 'cost-audit-auth',
      },
    })
  }
  return supabaseInstance
}

// ============================================================
// Auth 认证相关方法（账号登录体系）
// ============================================================

/**
 * 通过用户名查找邮箱
 * 用于将前端「账号登录」映射到 Supabase Auth 的邮箱密码认证
 */
export async function findEmailByUsername(username: string): Promise<string | null> {
  const client = getSupabaseClient()
  const { data, error } = await client
    .from(USER_PROFILES_TABLE)
    .select('email')
    .eq('username', username)
    .eq('is_active', true)
    .single()

  if (error || !data) return null
  return data.email
}

/**
 * 账号登录：输入 username + password → 查找 email → Supabase Auth 认证
 */
export async function signInWithUsername(username: string, password: string) {
  const email = await findEmailByUsername(username)
  if (!email) {
    throw new Error('账号不存在或已被禁用')
  }
  return signIn(email, password)
}

/**
 * 邮箱密码登录（内部使用，由 signInWithUsername 调用）
 */
async function signIn(email: string, password: string) {
  const client = getSupabaseClient()
  const { data, error } = await client.auth.signInWithPassword({
    email,
    password,
  })
  if (error) throw error
  return data
}

/**
 * 管理员创建用户：在 auth.users 注册 + 写入 user_profiles
 */
export async function signUpWithProfile(dto: CreateAdminUserDto) {
  const client = getSupabaseClient()

  // 1. Supabase Auth 注册
  const { data: authData, error: authError } = await client.auth.signUp({
    email: dto.email,
    password: dto.password,
    options: {
      data: { display_name: dto.displayName },
    },
  })
  if (authError) throw authError
  if (!authData.user) throw new Error('注册失败：未返回用户信息')

  const userId = authData.user.id

  // 2. 写入 user_profiles 表
  const { error: profileError } = await client
    .from(USER_PROFILES_TABLE)
    .insert({
      user_id: userId,
      username: dto.username,
      display_name: dto.displayName,
      email: dto.email,
      role: dto.role,
      is_active: true,
    })

  if (profileError) throw profileError

  return { userId, username: dto.username }
}

/**
 * 用户登出
 */
export async function signOut() {
  const client = getSupabaseClient()
  const { error } = await client.auth.signOut()
  if (error) throw error
}

/**
 * 获取当前会话（含 user_profiles 扩展信息）
 */
export async function getSession(): Promise<AuthSession | null> {
  const client = getSupabaseClient()
  const { data } = await client.auth.getSession()
  if (!data.session) return null

  // 查询 user_profiles 获取 username 和 role
  const { data: profile } = await client
    .from(USER_PROFILES_TABLE)
    .select('username, role')
    .eq('user_id', data.session.user.id)
    .maybeSingle()

  return {
    accessToken: data.session.access_token,
    refreshToken: data.session.refresh_token ?? '',
    expiresAt: data.session.expires_at ?? 0,
    user: {
      id: data.session.user.id,
      email: data.session.user.email ?? '',
      displayName:
        (data.session.user.user_metadata as Record<string, string>)?.display_name ??
        profile?.username ??
        '',
      createdAt: data.session.user.created_at,
      username: profile?.username ?? '',
      role: (profile?.role as AdminRole) ?? 'viewer',
    },
  }
}

/**
 * 监听认证状态变化
 */
export function onAuthStateChange(callback: (session: AuthSession | null) => void) {
  const client = getSupabaseClient()
  const { data } = client.auth.onAuthStateChange(async (_event, session) => {
    if (!session) {
      callback(null)
      return
    }

    // 查询 user_profiles 补充 username / role
    const { data: profile } = await client
      .from(USER_PROFILES_TABLE)
      .select('username, role')
      .eq('user_id', session.user.id)
      .maybeSingle()

    callback({
      accessToken: session.access_token,
      refreshToken: session.refresh_token ?? '',
      expiresAt: session.expires_at ?? 0,
      user: {
        id: session.user.id,
        email: session.user.email ?? '',
        displayName:
          (session.user.user_metadata as Record<string, string>)?.display_name ??
          profile?.username ??
          '',
        createdAt: session.user.created_at,
        username: profile?.username ?? '',
        role: (profile?.role as AdminRole) ?? 'viewer',
      },
    })
  })
  return data
}

/**
 * 获取当前登录用户信息
 */
export async function getCurrentUser(): Promise<UserProfile | null> {
  const session = await getSession()
  return session?.user ?? null
}

/**
 * 判断当前是否已登录
 */
export function isAuthenticated(): boolean {
  const client = getSupabaseClient()
  return client.auth.getSession() !== null
}

/**
 * 写操作权限检查：未登录时抛出可识别错误
 */
export function requireAuthForMutation(operation = '该操作'): void {
  const client = getSupabaseClient()
  if (!client.auth.getSession()) {
    throw new Error(`UNAUTHORIZED: 请先登录后再进行${operation}`)
  }
}

/**
 * 判断当前用户是否为管理员
 */
export async function isCurrentUserAdmin(): Promise<boolean> {
  const user = await getCurrentUser()
  return user?.role === 'admin'
}

// ============================================================
// 管理员 — 用户管理 API
// ============================================================
export async function getAdminUsers(): Promise<AdminUser[]> {
  const client = getSupabaseClient()
  const { data, error } = await client
    .from(USER_PROFILES_TABLE)
    .select('*')
    .order('created_at', { ascending: false })

  if (error) throw error

  return (data ?? []).map((row: Record<string, unknown>) => ({
    id: row.id as string,
    userId: row.user_id as string,
    username: row.username as string,
    displayName: row.display_name as string,
    email: row.email as string,
    role: row.role as AdminRole,
    isActive: row.is_active as boolean,
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  }))
}

/**
 * 更新用户信息（角色、启用/禁用等）
 */
export async function updateAdminUser(dto: UpdateAdminUserDto): Promise<void> {
  const client = getSupabaseClient()
  const updates: Record<string, unknown> = {
    updated_at: new Date().toISOString(),
  }

  if (dto.username !== undefined) updates.username = dto.username
  if (dto.displayName !== undefined) updates.display_name = dto.displayName
  if (dto.email !== undefined) updates.email = dto.email
  if (dto.role !== undefined) updates.role = dto.role
  if (dto.isActive !== undefined) updates.is_active = dto.isActive

  const { error } = await client
    .from(USER_PROFILES_TABLE)
    .update(updates)
    .eq('id', dto.id)

  if (error) throw error
}

/**
 * 删除用户（软删除：标记 is_active = false）
 */
export async function deactivateUser(profileId: string): Promise<void> {
  const client = getSupabaseClient()
  const { error } = await client
    .from(USER_PROFILES_TABLE)
    .update({ is_active: false, updated_at: new Date().toISOString() })
    .eq('id', profileId)

  if (error) throw error
}

// ============================================================
// 管理员 — 系统设置 API
// ============================================================

/**
 * 获取单个系统设置
 */
export async function getSystemSetting(key: SystemSettingKey): Promise<SystemSetting | null> {
  const client = getSupabaseClient()
  const { data, error } = await client
    .from(SYSTEM_SETTINGS_TABLE)
    .select('*')
    .eq('key', key)
    .maybeSingle()

  if (error || !data) return null
  return {
    key: data.key as SystemSettingKey,
    value: data.value as SystemSettingValue,
    updatedAt: data.updated_at as string,
    updatedBy: (data.updated_by as string) ?? '',
  }
}

/**
 * 获取所有系统设置
 */
export async function getAllSystemSettings(): Promise<SystemSetting[]> {
  const client = getSupabaseClient()
  const { data, error } = await client
    .from(SYSTEM_SETTINGS_TABLE)
    .select('*')
    .order('key')

  if (error) return []

  return (data ?? []).map((row: Record<string, unknown>) => ({
    key: row.key as SystemSettingKey,
    value: row.value as SystemSettingValue,
    updatedAt: row.updated_at as string,
    updatedBy: (row.updated_by as string) ?? '',
  }))
}

/**
 * 更新系统设置
 */
export async function setSystemSetting(
  key: SystemSettingKey,
  value: SystemSettingValue,
  updatedBy: string
): Promise<void> {
  const client = getSupabaseClient()
  const { error } = await client
    .from(SYSTEM_SETTINGS_TABLE)
    .upsert(
      {
        key,
        value,
        updated_at: new Date().toISOString(),
        updated_by: updatedBy,
      },
      { onConflict: 'key' }
    )

  if (error) throw error
}

/**
 * 获取管理员统计数据
 */
export async function getAdminStats(): Promise<AdminStats> {
  const client = getSupabaseClient()

  const [profilesResult, itemsResult] = await Promise.allSettled([
    client.from(USER_PROFILES_TABLE).select('role, is_active'),
    client.from(TABLE_NAME).select('id', { count: 'exact', head: true }),
  ])

  let totalUsers = 0
  let activeUsers = 0
  let adminCount = 0

  if (profilesResult.status === 'fulfilled' && profilesResult.value.data) {
    const profiles = profilesResult.value.data as Record<string, unknown>[]
    totalUsers = profiles.length
    activeUsers = profiles.filter((p) => p.is_active === true).length
    adminCount = profiles.filter((p) => p.role === 'admin').length
  }

  const totalProjects =
    itemsResult.status === 'fulfilled' && itemsResult.value.count ? itemsResult.value.count : 0

  return {
    totalUsers,
    activeUsers,
    adminCount,
    totalProjects,
    recentLogins: 0, // 需要单独的登录日志表，暂不实现
  }
}

// ============================================================
// SQL 建表语句（Supabase PostgreSQL）
// ============================================================

/**
 * SQL 建表语句（在 Supabase SQL Editor 中执行）
 */
export const CREATE_TABLE_SQL = `
-- ============================================================
-- 1. 业务数据表
-- ============================================================
CREATE TABLE IF NOT EXISTS ${TABLE_NAME} (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  data JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_items_stage ON ${TABLE_NAME} ((data->>'stage'));
CREATE INDEX IF NOT EXISTS idx_items_priority ON ${TABLE_NAME} ((data->>'priority'));
CREATE INDEX IF NOT EXISTS idx_items_category ON ${TABLE_NAME} ((data->>'category'));

-- ============================================================
-- 2. 用户资料表（账号登录 + 角色管理）
-- ============================================================
CREATE TABLE IF NOT EXISTS ${USER_PROFILES_TABLE} (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE NOT NULL,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  email TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin', 'editor', 'viewer')),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_profiles_username ON ${USER_PROFILES_TABLE} (username);
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON ${USER_PROFILES_TABLE} (user_id);

-- ============================================================
-- 3. 系统设置表
-- ============================================================
CREATE TABLE IF NOT EXISTS ${SYSTEM_SETTINGS_TABLE} (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  updated_by TEXT
);

-- 默认系统设置
INSERT INTO ${SYSTEM_SETTINGS_TABLE} (key, value, updated_by)
VALUES 
  ('registration_open', '{"enabled": false, "requireApproval": true}'::jsonb, 'system'),
  ('login_rules', '{"minPasswordLength": 1, "maxLoginAttempts": 5, "sessionTimeoutMinutes": 480, "allowConcurrentSessions": true}'::jsonb, 'system'),
  ('system_name', '"造价结算审计看板"'::jsonb, 'system')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- 4. 初始管理员账号（开发/测试用，生产部署请修改密码）
-- ============================================================
DO $$
DECLARE
  v_user_id UUID;
BEGIN
  INSERT INTO auth.users (
    id, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
    phone_confirmed_at, confirmation_sent_at
  )
  VALUES (
    gen_random_uuid(), 'admin@jijian.com', crypt('admin', gen_salt('bf')), NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"系统管理员"}'::jsonb, NOW(), NOW(), NOW(), NOW()
  )
  ON CONFLICT (email) DO NOTHING
  RETURNING id INTO v_user_id;

  IF v_user_id IS NOT NULL THEN
    INSERT INTO ${USER_PROFILES_TABLE} (user_id, username, display_name, email, role, is_active)
    VALUES (v_user_id, 'admin', '系统管理员', 'admin@jijian.com', 'admin', true);
  END IF;
END $$;

-- ============================================================
-- 5. RLS（Row Level Security）策略
-- ============================================================
ALTER TABLE ${USER_PROFILES_TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE ${SYSTEM_SETTINGS_TABLE} ENABLE ROW LEVEL SECURITY;

-- user_profiles: 允许公开按 username 查询（用于登录时查找 email）
CREATE POLICY "Allow public username lookup"
  ON ${USER_PROFILES_TABLE}
  FOR SELECT
  USING (true);

-- user_profiles: 仅管理员可增删改
CREATE POLICY "Allow admin manage users"
  ON ${USER_PROFILES_TABLE}
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM ${USER_PROFILES_TABLE} up
      WHERE up.user_id = auth.uid() AND up.role = 'admin' AND up.is_active = true
    )
  );

-- system_settings: 所有人可读
CREATE POLICY "Allow all read settings"
  ON ${SYSTEM_SETTINGS_TABLE}
  FOR SELECT
  USING (true);

-- system_settings: 仅管理员可写
CREATE POLICY "Allow admin write settings"
  ON ${SYSTEM_SETTINGS_TABLE}
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM ${USER_PROFILES_TABLE} up
      WHERE up.user_id = auth.uid() AND up.role = 'admin' AND up.is_active = true
    )
  );
`

// ============================================================
// 数据表检测与初始化
// ============================================================

/**
 * 检查表是否存在，不存在则建表
 */
export async function ensureTableExists(): Promise<boolean> {
  try {
    const client = getSupabaseClient()
    const { error } = await client
      .from(TABLE_NAME)
      .select('id', { count: 'exact', head: true })

    if (error && error.code === '42P01') {
      console.warn('[Supabase] 数据表不存在，请在 Supabase SQL Editor 执行 CREATE_TABLE_SQL')
      return false
    }
    return true
  } catch {
    return false
  }
}

// ============================================================
// 数据序列化工具
// ============================================================

export function rowToItem(row: { id: string; data: CostAuditItem; updated_at: string }): CostAuditItem {
  return {
    ...row.data,
    id: row.id,
  }
}

export function itemToRow(item: CostAuditItem): { data: CostAuditItem } {
  return { data: item }
}
