-- ============================================================
-- 造价结算审计看板 — 数据库初始化 SQL
-- 在 Supabase SQL Editor 中全选执行即可
-- ============================================================

-- ============================================================
-- 1. 业务数据表（造价项目）
-- ============================================================
CREATE TABLE IF NOT EXISTS cost_audit_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  data JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_items_stage ON cost_audit_items ((data->>'stage'));
CREATE INDEX IF NOT EXISTS idx_items_priority ON cost_audit_items ((data->>'priority'));
CREATE INDEX IF NOT EXISTS idx_items_category ON cost_audit_items ((data->>'category'));

-- ============================================================
-- 2. 用户资料表（账号登录 + 角色管理）
--    user_id → auth.users(id)    username → 登录账号名
-- ============================================================
CREATE TABLE IF NOT EXISTS user_profiles (
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

CREATE INDEX IF NOT EXISTS idx_profiles_username ON user_profiles (username);
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON user_profiles (user_id);

-- ============================================================
-- 3. 系统设置表
--    注册开关、登录规则等全局参数
-- ============================================================
CREATE TABLE IF NOT EXISTS system_settings (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  updated_by TEXT
);

-- 默认系统设置
INSERT INTO system_settings (key, value, updated_by)
VALUES 
  ('registration_open', '{"enabled": false, "requireApproval": true}'::jsonb, 'system'),
  ('login_rules', '{"minPasswordLength": 1, "maxLoginAttempts": 5, "sessionTimeoutMinutes": 480, "allowConcurrentSessions": true}'::jsonb, 'system'),
  ('system_name', '"造价结算审计看板"'::jsonb, 'system')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- 4. 初始管理员账号（开发/测试用，生产部署请修改密码）
-- ============================================================
-- 说明：
--   1. 下方脚本直接在 auth.users 创建用户 admin / admin
--   2. 并在 user_profiles 中关联为 role='admin'
--   3. 生产环境请删除/修改此默认账号，或在 Supabase Dashboard 手动创建
-- ============================================================
DO $$
DECLARE
  v_user_id UUID;
BEGIN
  -- 1. 创建 auth 用户（邮箱确认状态设为已确认）
  INSERT INTO auth.users (
    id,
    email,
    encrypted_password,
    email_confirmed_at,
    raw_app_meta_data,
    raw_user_meta_data,
    created_at,
    updated_at,
    phone_confirmed_at,
    confirmation_sent_at
  )
  VALUES (
    gen_random_uuid(),
    'admin@jijian.com',
    crypt('admin', gen_salt('bf')),
    NOW(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"系统管理员"}'::jsonb,
    NOW(),
    NOW(),
    NOW(),
    NOW()
  )
  ON CONFLICT (email) DO NOTHING
  RETURNING id INTO v_user_id;

  -- 2. 如果用户是新创建的，则插入 user_profiles
  IF v_user_id IS NOT NULL THEN
    INSERT INTO user_profiles (user_id, username, display_name, email, role, is_active)
    VALUES (v_user_id, 'admin', '系统管理员', 'admin@jijian.com', 'admin', true);
  END IF;
END $$;

-- ============================================================
-- 5. RLS（Row Level Security）策略
-- ============================================================
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;

-- user_profiles: 允许公开按 username 查询（用于登录时账号→邮箱映射）
CREATE POLICY "Allow public username lookup"
  ON user_profiles
  FOR SELECT
  USING (true);

-- user_profiles: 仅管理员可增删改
CREATE POLICY "Allow admin manage users"
  ON user_profiles
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles up
      WHERE up.user_id = auth.uid() AND up.role = 'admin' AND up.is_active = true
    )
  );

-- system_settings: 所有人可读
CREATE POLICY "Allow all read settings"
  ON system_settings
  FOR SELECT
  USING (true);

-- system_settings: 仅管理员可写
CREATE POLICY "Allow admin write settings"
  ON system_settings
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM user_profiles up
      WHERE up.user_id = auth.uid() AND up.role = 'admin' AND up.is_active = true
    )
  );
