PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  checksum TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT DEFAULT '',
  success INTEGER NOT NULL DEFAULT 0
);

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
  contract_date TEXT DEFAULT '',
  construction_unit TEXT DEFAULT '',
  contractor_name TEXT DEFAULT '',
  contractor_contact TEXT DEFAULT '',
  owner_unit TEXT DEFAULT '',
  company_role TEXT DEFAULT '',
  manager_name TEXT DEFAULT '',
  project_status TEXT DEFAULT 'awarded',
  lifecycle_version INTEGER NOT NULL DEFAULT 0,
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
  settlement_status TEXT DEFAULT 'not_started',
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

CREATE TABLE IF NOT EXISTS settlement_payment_nodes (
  id TEXT PRIMARY KEY,
  settlement_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  node_name TEXT NOT NULL,
  node_order INTEGER DEFAULT 0,
  trigger_condition TEXT DEFAULT '',
  base_type TEXT DEFAULT '',
  payment_ratio REAL DEFAULT 0,
  base_amount REAL DEFAULT 0,
  calculated_amount REAL DEFAULT 0,
  is_cumulative INTEGER DEFAULT 1,
  deduct_existing INTEGER DEFAULT 1,
  required_documents_json TEXT DEFAULT '[]',
  due_days INTEGER DEFAULT 30,
  reminder_enabled INTEGER DEFAULT 1,
  node_status TEXT DEFAULT '未满足',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (settlement_id) REFERENCES project_settlements(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS project_lifecycle_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  from_stage TEXT NOT NULL,
  to_stage TEXT NOT NULL,
  transition_type TEXT NOT NULL DEFAULT 'forward',
  reason TEXT DEFAULT '',
  idempotency_key TEXT NOT NULL,
  lifecycle_version INTEGER NOT NULL,
  actor_id TEXT DEFAULT '',
  actor_name TEXT DEFAULT '',
  payload_json TEXT DEFAULT '{}',
  stage_form_snapshot_id TEXT,
  evidence_document_version_id TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
  UNIQUE (project_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  document_type TEXT NOT NULL,
  lifecycle_stage TEXT NOT NULL,
  project_id TEXT,
  candidate_project_id TEXT,
  status TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'user_upload',
  current_version_id TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id),
  FOREIGN KEY (candidate_project_id) REFERENCES project_records(id)
);

CREATE TABLE IF NOT EXISTS document_versions (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  version_no INTEGER NOT NULL,
  original_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  replaced_version_id TEXT,
  uploaded_by TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  UNIQUE (document_id, version_no),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (replaced_version_id) REFERENCES document_versions(id)
);

CREATE TABLE IF NOT EXISTS document_pages (
  id TEXT PRIMARY KEY,
  document_version_id TEXT NOT NULL,
  page_number INTEGER NOT NULL,
  relative_path TEXT NOT NULL,
  width_px INTEGER NOT NULL,
  height_px INTEGER NOT NULL,
  dpi INTEGER NOT NULL DEFAULT 300,
  rotation_degrees INTEGER NOT NULL DEFAULT 0,
  quality_score REAL,
  preprocessing_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (document_version_id, page_number),
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recognition_jobs (
  id TEXT PRIMARY KEY,
  document_version_id TEXT NOT NULL,
  status TEXT NOT NULL,
  adapter_key TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  model_version TEXT DEFAULT '',
  provider_request_id TEXT DEFAULT '',
  idempotency_key TEXT NOT NULL UNIQUE,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  lease_owner TEXT DEFAULT '',
  lease_expires_at TEXT DEFAULT '',
  next_attempt_at TEXT DEFAULT '',
  error_code TEXT DEFAULT '',
  error_message TEXT DEFAULT '',
  provider_metadata_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT DEFAULT '',
  finished_at TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source_recognition_job_id TEXT,
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id) ON DELETE CASCADE,
  FOREIGN KEY (source_recognition_job_id) REFERENCES recognition_jobs(id)
);

CREATE TABLE IF NOT EXISTS project_intake_drafts (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  document_id TEXT,
  document_version_id TEXT,
  schema_version TEXT NOT NULL DEFAULT 'contract.v1',
  values_json TEXT NOT NULL DEFAULT '{}',
  fallback_reason TEXT NOT NULL DEFAULT '',
  fallback_note TEXT NOT NULL DEFAULT '',
  completed_project_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id),
  FOREIGN KEY (completed_project_id) REFERENCES project_records(id)
);

CREATE TABLE IF NOT EXISTS ocr_blocks (
  id TEXT PRIMARY KEY,
  recognition_job_id TEXT NOT NULL,
  document_page_id TEXT NOT NULL,
  block_type TEXT NOT NULL,
  raw_text TEXT NOT NULL DEFAULT '',
  confidence REAL,
  bbox_json TEXT NOT NULL,
  row_index INTEGER,
  column_index INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (recognition_job_id) REFERENCES recognition_jobs(id) ON DELETE CASCADE,
  FOREIGN KEY (document_page_id) REFERENCES document_pages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS extracted_fields (
  id TEXT PRIMARY KEY,
  recognition_job_id TEXT NOT NULL,
  semantic_key TEXT NOT NULL,
  raw_value TEXT NOT NULL DEFAULT '',
  normalized_value_json TEXT NOT NULL DEFAULT 'null',
  confidence REAL,
  validation_status TEXT NOT NULL DEFAULT 'unvalidated',
  source_kind TEXT NOT NULL DEFAULT 'ocr',
  model_version TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE (recognition_job_id, semantic_key),
  FOREIGN KEY (recognition_job_id) REFERENCES recognition_jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence_anchors (
  id TEXT PRIMARY KEY,
  extracted_field_id TEXT NOT NULL,
  document_version_id TEXT NOT NULL,
  document_page_id TEXT NOT NULL,
  bbox_json TEXT NOT NULL,
  source_text TEXT NOT NULL DEFAULT '',
  image_crop_relative_path TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY (extracted_field_id) REFERENCES extracted_fields(id) ON DELETE CASCADE,
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id) ON DELETE CASCADE,
  FOREIGN KEY (document_page_id) REFERENCES document_pages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_reviews (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  document_version_id TEXT NOT NULL,
  recognition_job_id TEXT NOT NULL,
  project_id TEXT,
  candidate_project_id TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  review_version INTEGER NOT NULL DEFAULT 0,
  blockers_json TEXT NOT NULL DEFAULT '[]',
  warnings_json TEXT NOT NULL DEFAULT '[]',
  confirmation_idempotency_key TEXT UNIQUE,
  reviewer_id TEXT DEFAULT '',
  reviewer_name TEXT DEFAULT '',
  opened_at TEXT NOT NULL,
  confirmed_at TEXT DEFAULT '',
  updated_at TEXT NOT NULL,
  UNIQUE (document_version_id, recognition_job_id),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id) ON DELETE CASCADE,
  FOREIGN KEY (recognition_job_id) REFERENCES recognition_jobs(id) ON DELETE CASCADE,
  FOREIGN KEY (project_id) REFERENCES project_records(id),
  FOREIGN KEY (candidate_project_id) REFERENCES project_records(id)
);

CREATE TABLE IF NOT EXISTS review_decisions (
  id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL,
  extracted_field_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  ai_value_json TEXT NOT NULL DEFAULT 'null',
  confirmed_value_json TEXT NOT NULL DEFAULT 'null',
  reason TEXT DEFAULT '',
  reviewer_id TEXT NOT NULL,
  reviewer_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (review_id, extracted_field_id),
  FOREIGN KEY (review_id) REFERENCES document_reviews(id) ON DELETE CASCADE,
  FOREIGN KEY (extracted_field_id) REFERENCES extracted_fields(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_decision_history (
  id TEXT PRIMARY KEY,
  review_decision_id TEXT NOT NULL,
  review_id TEXT NOT NULL,
  extracted_field_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  ai_value_json TEXT NOT NULL DEFAULT 'null',
  confirmed_value_json TEXT NOT NULL DEFAULT 'null',
  reason TEXT DEFAULT '',
  reviewer_id TEXT NOT NULL,
  reviewer_name TEXT NOT NULL,
  revision_no INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (review_decision_id, revision_no),
  FOREIGN KEY (review_decision_id) REFERENCES review_decisions(id) ON DELETE CASCADE,
  FOREIGN KEY (review_id) REFERENCES document_reviews(id) ON DELETE CASCADE,
  FOREIGN KEY (extracted_field_id) REFERENCES extracted_fields(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stage_form_snapshots (
  id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL UNIQUE,
  project_id TEXT NOT NULL,
  stage_key TEXT NOT NULL,
  document_version_id TEXT NOT NULL,
  form_template_version TEXT NOT NULL,
  extraction_schema_version TEXT NOT NULL,
  values_json TEXT NOT NULL,
  evidence_manifest_json TEXT NOT NULL,
  confirmed_by TEXT NOT NULL,
  confirmed_by_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (review_id) REFERENCES document_reviews(id),
  FOREIGN KEY (project_id) REFERENCES project_records(id),
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id)
);

CREATE TABLE IF NOT EXISTS project_contracts (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_version_id TEXT NOT NULL,
  stage_form_snapshot_id TEXT NOT NULL,
  contract_name TEXT NOT NULL DEFAULT '',
  contract_number TEXT NOT NULL DEFAULT '',
  contract_type TEXT NOT NULL DEFAULT '',
  owner_unit TEXT NOT NULL,
  contractor_unit TEXT NOT NULL,
  project_manager TEXT NOT NULL DEFAULT '',
  contract_amount_fen INTEGER NOT NULL,
  signed_date TEXT NOT NULL,
  start_date TEXT DEFAULT '',
  end_date TEXT DEFAULT '',
  payment_terms_json TEXT NOT NULL DEFAULT '[]',
  retention_terms_json TEXT NOT NULL DEFAULT '[]',
  performance_bond_terms_json TEXT NOT NULL DEFAULT '[]',
  is_current INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id),
  FOREIGN KEY (stage_form_snapshot_id) REFERENCES stage_form_snapshots(id)
);

CREATE TABLE IF NOT EXISTS project_acceptance_records (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_version_id TEXT NOT NULL,
  stage_form_snapshot_id TEXT NOT NULL,
  conclusion TEXT NOT NULL,
  acceptance_date TEXT NOT NULL,
  completion_date TEXT DEFAULT '',
  contractor_unit TEXT NOT NULL DEFAULT '',
  supervisor_unit TEXT NOT NULL DEFAULT '',
  designer_unit TEXT NOT NULL DEFAULT '',
  contract_amount_reference_fen INTEGER,
  signature_status_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id),
  FOREIGN KEY (stage_form_snapshot_id) REFERENCES stage_form_snapshots(id)
);

CREATE TABLE IF NOT EXISTS project_audit_determinations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_version_id TEXT NOT NULL,
  stage_form_snapshot_id TEXT NOT NULL,
  audit_type TEXT NOT NULL DEFAULT '',
  submitted_amount_fen INTEGER,
  first_determined_amount_fen INTEGER,
  second_determined_amount_fen INTEGER,
  engineering_determined_amount_fen INTEGER NOT NULL,
  review_fee_deduction_fen INTEGER NOT NULL DEFAULT 0,
  final_settlement_amount_fen INTEGER NOT NULL,
  reduction_amount_fen INTEGER,
  reduction_rate_decimal TEXT DEFAULT '',
  determination_date TEXT NOT NULL,
  uppercase_amount TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
  FOREIGN KEY (document_version_id) REFERENCES document_versions(id),
  FOREIGN KEY (stage_form_snapshot_id) REFERENCES stage_form_snapshots(id)
);

CREATE TRIGGER IF NOT EXISTS trg_lifecycle_event_evidence_insert
BEFORE INSERT ON project_lifecycle_events
BEGIN
  SELECT CASE
    WHEN NEW.stage_form_snapshot_id IS NOT NULL
     AND NEW.stage_form_snapshot_id <> ''
     AND NOT EXISTS (
       SELECT 1 FROM stage_form_snapshots WHERE id = NEW.stage_form_snapshot_id
     )
    THEN RAISE(ABORT, 'invalid stage_form_snapshot_id')
  END;
  SELECT CASE
    WHEN NEW.evidence_document_version_id IS NOT NULL
     AND NEW.evidence_document_version_id <> ''
     AND NOT EXISTS (
       SELECT 1 FROM document_versions WHERE id = NEW.evidence_document_version_id
     )
    THEN RAISE(ABORT, 'invalid evidence_document_version_id')
  END;
END;

CREATE TRIGGER IF NOT EXISTS trg_lifecycle_event_evidence_update
BEFORE UPDATE OF stage_form_snapshot_id, evidence_document_version_id
ON project_lifecycle_events
BEGIN
  SELECT CASE
    WHEN NEW.stage_form_snapshot_id IS NOT NULL
     AND NEW.stage_form_snapshot_id <> ''
     AND NOT EXISTS (
       SELECT 1 FROM stage_form_snapshots WHERE id = NEW.stage_form_snapshot_id
     )
    THEN RAISE(ABORT, 'invalid stage_form_snapshot_id')
  END;
  SELECT CASE
    WHEN NEW.evidence_document_version_id IS NOT NULL
     AND NEW.evidence_document_version_id <> ''
     AND NOT EXISTS (
       SELECT 1 FROM document_versions WHERE id = NEW.evidence_document_version_id
     )
    THEN RAISE(ABORT, 'invalid evidence_document_version_id')
  END;
END;

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
  table_width INTEGER DEFAULT 140,
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
CREATE INDEX IF NOT EXISTS idx_settlement_payment_nodes_settlement ON settlement_payment_nodes(settlement_id, node_order);
CREATE INDEX IF NOT EXISTS idx_project_variations_project ON project_variations(project_id, variation_status);
CREATE INDEX IF NOT EXISTS idx_project_lifecycle_events_project ON project_lifecycle_events(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_project_type ON documents(project_id, document_type, status);
CREATE INDEX IF NOT EXISTS idx_document_versions_hash ON document_versions(sha256);
CREATE INDEX IF NOT EXISTS idx_document_pages_version ON document_pages(document_version_id, page_number);
CREATE INDEX IF NOT EXISTS idx_recognition_jobs_status ON recognition_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_project_intake_drafts_owner ON project_intake_drafts(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_intake_drafts_status ON project_intake_drafts(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_extracted_fields_job_key ON extracted_fields(recognition_job_id, semantic_key);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON document_reviews(status, opened_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_contracts_current ON project_contracts(project_id) WHERE is_current = 1;
CREATE TRIGGER IF NOT EXISTS trg_stage_form_snapshots_immutable_update
BEFORE UPDATE ON stage_form_snapshots
BEGIN
  SELECT RAISE(ABORT, 'stage form snapshots are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_stage_form_snapshots_immutable_delete
BEFORE DELETE ON stage_form_snapshots
BEGIN
  SELECT RAISE(ABORT, 'stage form snapshots are immutable');
END;
CREATE TRIGGER IF NOT EXISTS trg_project_contract_document_unique
BEFORE INSERT ON project_contracts
WHEN EXISTS (
  SELECT 1
  FROM project_contracts existing_contract
  JOIN document_versions existing_version
    ON existing_version.id = existing_contract.document_version_id
  JOIN document_versions new_version
    ON new_version.id = NEW.document_version_id
  WHERE existing_version.sha256 = new_version.sha256
)
BEGIN
  SELECT RAISE(ABORT, 'contract document already created a project');
END;
CREATE INDEX IF NOT EXISTS idx_audit_field_configs_sort ON audit_field_configs(entity_type, sort_order);
CREATE INDEX IF NOT EXISTS idx_audit_field_options_group ON audit_field_options(group_key, sort_order);
CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_operation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_users_username ON system_users(username);
