PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS audit_projects (
  id TEXT PRIMARY KEY,
  project_id TEXT DEFAULT '',
  project_code TEXT DEFAULT '',
  project_name TEXT NOT NULL,
  audited_unit TEXT DEFAULT '',
  audit_type TEXT DEFAULT '',
  section_building TEXT DEFAULT '',
  settlement_no TEXT DEFAULT '',
  category TEXT DEFAULT '',
  priority TEXT DEFAULT 'S2',
  contractor_name TEXT DEFAULT '',
  contractor_phone TEXT DEFAULT '',
  first_audit_company TEXT DEFAULT '',
  first_auditor_name TEXT DEFAULT '',
  second_audit_department TEXT DEFAULT '',
  second_auditor_name TEXT DEFAULT '',
  contract_amount REAL DEFAULT 0,
  submitted_amount REAL DEFAULT 0,
  first_audit_amount REAL DEFAULT 0,
  second_audit_amount REAL DEFAULT 0,
  audit_difference REAL DEFAULT 0,
  final_payable REAL DEFAULT 0,
  paid_amount REAL DEFAULT 0,
  submit_date TEXT DEFAULT '',
  audit_deadline TEXT DEFAULT '',
  start_date TEXT DEFAULT '',
  planned_end_date TEXT DEFAULT '',
  actual_end_date TEXT DEFAULT '',
  doc_status TEXT DEFAULT '',
  current_stage TEXT DEFAULT 'submitted',
  status TEXT DEFAULT 'active',
  progress_percent INTEGER DEFAULT 0,
  manager_name TEXT DEFAULT '',
  is_delayed INTEGER DEFAULT 0,
  delay_days INTEGER DEFAULT 0,
  description TEXT DEFAULT '',
  remark_dispute TEXT DEFAULT '',
  remark_coordination TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0,
  is_archived INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_records (
  id TEXT PRIMARY KEY,
  project_code TEXT UNIQUE NOT NULL,
  project_name TEXT NOT NULL,
  construction_unit TEXT DEFAULT '',
  contractor_name TEXT DEFAULT '',
  contractor_contact TEXT DEFAULT '',
  owner_unit TEXT DEFAULT '',
  company_role TEXT DEFAULT '',
  manager_name TEXT DEFAULT '',
  project_status TEXT DEFAULT 'active',
  settlement_status TEXT DEFAULT 'not_started',
  audit_stage TEXT DEFAULT 'not_linked',
  contract_amount REAL DEFAULT 0,
  submitted_amount REAL DEFAULT 0,
  paid_amount REAL DEFAULT 0,
  payment_terms TEXT DEFAULT '',
  planned_start_date TEXT DEFAULT '',
  planned_end_date TEXT DEFAULT '',
  description TEXT DEFAULT '',
  document_completion REAL DEFAULT 0,
  missing_required_count INTEGER DEFAULT 0,
  settlement_book_status TEXT DEFAULT 'missing',
  first_audit_material_status TEXT DEFAULT 'missing',
  second_audit_material_status TEXT DEFAULT 'missing',
  variation_count INTEGER DEFAULT 0,
  variation_amount REAL DEFAULT 0,
  audit_project_id TEXT DEFAULT '',
  created_by TEXT DEFAULT '',
  updated_by TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT DEFAULT '',
  is_deleted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS project_document_categories (
  id TEXT PRIMARY KEY,
  category_key TEXT UNIQUE NOT NULL,
  category_name TEXT NOT NULL,
  description TEXT DEFAULT '',
  required INTEGER DEFAULT 1,
  sort_order INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_files (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  category_key TEXT NOT NULL,
  display_name TEXT NOT NULL,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  file_ext TEXT DEFAULT '',
  mime_type TEXT DEFAULT '',
  file_size INTEGER DEFAULT 0,
  relative_path TEXT NOT NULL,
  version_no INTEGER DEFAULT 1,
  is_current INTEGER DEFAULT 1,
  uploaded_by TEXT DEFAULT '',
  uploaded_by_name TEXT DEFAULT '',
  uploaded_at TEXT NOT NULL,
  renamed_at TEXT DEFAULT '',
  deleted_at TEXT DEFAULT '',
  is_deleted INTEGER DEFAULT 0,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_settlements (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  settlement_name TEXT NOT NULL,
  settlement_type TEXT DEFAULT 'progress',
  settlement_status TEXT DEFAULT 'pending',
  apply_amount REAL DEFAULT 0,
  approved_amount REAL DEFAULT 0,
  paid_amount REAL DEFAULT 0,
  apply_date TEXT DEFAULT '',
  expected_pay_date TEXT DEFAULT '',
  paid_date TEXT DEFAULT '',
  remark TEXT DEFAULT '',
  created_by TEXT DEFAULT '',
  updated_by TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT DEFAULT '',
  is_deleted INTEGER DEFAULT 0,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_variations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  variation_name TEXT NOT NULL,
  variation_type TEXT DEFAULT 'change',
  variation_status TEXT DEFAULT 'pending',
  amount REAL DEFAULT 0,
  occurred_date TEXT DEFAULT '',
  approved_date TEXT DEFAULT '',
  remark TEXT DEFAULT '',
  created_by TEXT DEFAULT '',
  updated_by TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT DEFAULT '',
  is_deleted INTEGER DEFAULT 0,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_operation_logs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  action TEXT NOT NULL,
  content TEXT DEFAULT '',
  operator_id TEXT DEFAULT '',
  operator_name TEXT DEFAULT '',
  before_json TEXT DEFAULT '{}',
  after_json TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_project_stages (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  stage_code TEXT NOT NULL,
  stage_name TEXT NOT NULL,
  stage_order INTEGER DEFAULT 0,
  entered_at TEXT NOT NULL,
  finished_at TEXT,
  start_date TEXT DEFAULT '',
  end_date TEXT DEFAULT '',
  owner TEXT DEFAULT '',
  handler_name TEXT DEFAULT '',
  status TEXT DEFAULT 'active',
  progress_percent INTEGER DEFAULT 0,
  remark TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0,
  created_at TEXT DEFAULT '',
  updated_at TEXT DEFAULT '',
  FOREIGN KEY (project_id) REFERENCES audit_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_project_logs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  action TEXT NOT NULL,
  log_type TEXT DEFAULT '',
  content TEXT DEFAULT '',
  operator TEXT DEFAULT '',
  operator_name TEXT DEFAULT '',
  note TEXT DEFAULT '',
  before_json TEXT DEFAULT '{}',
  after_json TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES audit_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_project_attachments (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_url TEXT NOT NULL,
  file_type TEXT DEFAULT '',
  original_name TEXT DEFAULT '',
  stored_name TEXT DEFAULT '',
  file_ext TEXT DEFAULT '',
  mime_type TEXT DEFAULT '',
  file_size INTEGER DEFAULT 0,
  relative_path TEXT DEFAULT '',
  uploaded_by TEXT DEFAULT '',
  uploaded_by_name TEXT DEFAULT '',
  uploaded_at TEXT NOT NULL,
  created_at TEXT DEFAULT '',
  deleted_at TEXT DEFAULT '',
  is_deleted INTEGER DEFAULT 0,
  FOREIGN KEY (project_id) REFERENCES audit_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_field_configs (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL DEFAULT 'project',
  field_key TEXT NOT NULL,
  field_label TEXT NOT NULL,
  field_name TEXT DEFAULT '',
  field_type TEXT NOT NULL DEFAULT 'text',
  module TEXT DEFAULT 'project',
  display_scene TEXT DEFAULT '',
  stage_key TEXT DEFAULT '',
  option_group TEXT DEFAULT '',
  bind_field TEXT DEFAULT '',
  required INTEGER DEFAULT 0,
  is_required INTEGER DEFAULT 0,
  visible_in_card INTEGER DEFAULT 1,
  visible_in_table INTEGER DEFAULT 1,
  visible_in_detail INTEGER DEFAULT 1,
  visible_in_form INTEGER DEFAULT 1,
  visible_in_gantt INTEGER DEFAULT 0,
  placeholder TEXT DEFAULT '',
  default_value TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1,
  is_enabled INTEGER DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(entity_type, field_key)
);

CREATE TABLE IF NOT EXISTS audit_field_options (
  id TEXT PRIMARY KEY,
  group_key TEXT NOT NULL,
  field_key TEXT DEFAULT '',
  option_label TEXT NOT NULL,
  option_value TEXT NOT NULL,
  color TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1,
  is_enabled INTEGER DEFAULT 1,
  is_system INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(group_key, option_value)
);

CREATE TABLE IF NOT EXISTS audit_project_field_values (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  field_key TEXT NOT NULL,
  field_value TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, field_key),
  FOREIGN KEY (project_id) REFERENCES audit_projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_stage_field_values (
  id TEXT PRIMARY KEY,
  stage_id TEXT NOT NULL,
  project_id TEXT DEFAULT '',
  field_key TEXT NOT NULL,
  field_value TEXT DEFAULT '',
  created_at TEXT DEFAULT '',
  updated_at TEXT NOT NULL,
  UNIQUE(stage_id, field_key),
  FOREIGN KEY (stage_id) REFERENCES audit_project_stages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  email TEXT DEFAULT '',
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer',
  is_active INTEGER DEFAULT 1,
  last_login_at TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_settings (
  setting_key TEXT PRIMARY KEY,
  setting_value TEXT NOT NULL,
  setting_group TEXT DEFAULT 'system',
  description TEXT DEFAULT '',
  updated_by TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_operation_logs (
  id TEXT PRIMARY KEY,
  user_id TEXT DEFAULT '',
  username TEXT DEFAULT '',
  role TEXT DEFAULT '',
  action TEXT NOT NULL,
  target_type TEXT DEFAULT '',
  target_id TEXT DEFAULT '',
  result TEXT DEFAULT 'success',
  ip_address TEXT DEFAULT '',
  user_agent TEXT DEFAULT '',
  detail_json TEXT DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_theme_configs (
  id TEXT PRIMARY KEY,
  theme_key TEXT UNIQUE NOT NULL,
  theme_name TEXT NOT NULL,
  package_name TEXT NOT NULL,
  preview_colors TEXT DEFAULT '[]',
  apply_scope TEXT DEFAULT 'global',
  is_enabled INTEGER DEFAULT 1,
  is_default INTEGER DEFAULT 0,
  dark_mode_enabled INTEGER DEFAULT 0,
  compact_mode_enabled INTEGER DEFAULT 0,
  sort_order INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_projects_stage ON audit_projects(current_stage);
CREATE INDEX IF NOT EXISTS idx_audit_projects_updated ON audit_projects(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_records_status ON project_records(project_status, settlement_status);
CREATE INDEX IF NOT EXISTS idx_project_records_updated ON project_records(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_files_project ON project_files(project_id, category_key, is_current);
CREATE INDEX IF NOT EXISTS idx_project_settlements_project ON project_settlements(project_id, settlement_status);
CREATE INDEX IF NOT EXISTS idx_project_variations_project ON project_variations(project_id, variation_status);
CREATE INDEX IF NOT EXISTS idx_audit_field_configs_sort ON audit_field_configs(entity_type, sort_order);
CREATE INDEX IF NOT EXISTS idx_audit_field_options_group ON audit_field_options(group_key, sort_order);
CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_operation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_users_username ON system_users(username);
