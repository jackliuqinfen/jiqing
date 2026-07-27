-- PostgreSQL migration baseline for 江苏集庆·工程管理系统.
-- This file mirrors the current SQLite schema plus the planned attachment metadata shape.
-- It is preparation material only; the running production service still uses SQLite.

CREATE TABLE IF NOT EXISTS audit_projects (
  id TEXT PRIMARY KEY,
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
  contract_amount NUMERIC DEFAULT 0,
  submitted_amount NUMERIC DEFAULT 0,
  first_audit_amount NUMERIC DEFAULT 0,
  second_audit_amount NUMERIC DEFAULT 0,
  audit_difference NUMERIC DEFAULT 0,
  final_payable NUMERIC DEFAULT 0,
  paid_amount NUMERIC DEFAULT 0,
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
  is_delayed BOOLEAN DEFAULT FALSE,
  delay_days INTEGER DEFAULT 0,
  description TEXT DEFAULT '',
  remark_dispute TEXT DEFAULT '',
  remark_coordination TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0,
  is_archived BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_project_stages (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES audit_projects(id) ON DELETE CASCADE,
  stage_code TEXT NOT NULL,
  stage_name TEXT NOT NULL,
  stage_order INTEGER DEFAULT 0,
  entered_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  start_date TEXT DEFAULT '',
  end_date TEXT DEFAULT '',
  owner TEXT DEFAULT '',
  handler_name TEXT DEFAULT '',
  status TEXT DEFAULT 'active',
  progress_percent INTEGER DEFAULT 0,
  remark TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_project_logs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES audit_projects(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  log_type TEXT DEFAULT '',
  content TEXT DEFAULT '',
  operator TEXT DEFAULT '',
  operator_name TEXT DEFAULT '',
  note TEXT DEFAULT '',
  before_json JSONB DEFAULT '{}'::jsonb,
  after_json JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_project_attachments (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES audit_projects(id) ON DELETE CASCADE,
  file_name TEXT DEFAULT '',
  file_url TEXT DEFAULT '',
  file_type TEXT DEFAULT '',
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  file_ext TEXT DEFAULT '',
  mime_type TEXT DEFAULT '',
  file_size BIGINT DEFAULT 0,
  relative_path TEXT NOT NULL,
  uploaded_by TEXT DEFAULT '',
  uploaded_by_name TEXT DEFAULT '',
  uploaded_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  deleted_at TIMESTAMPTZ,
  is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS desktop_sync_hash_cache (
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  revision_key TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  file_size BIGINT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (source_type, source_id, revision_key)
);

CREATE INDEX IF NOT EXISTS idx_desktop_sync_hash_updated
  ON desktop_sync_hash_cache(updated_at);

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
  required BOOLEAN DEFAULT FALSE,
  is_required BOOLEAN DEFAULT FALSE,
  visible_in_card BOOLEAN DEFAULT TRUE,
  visible_in_table BOOLEAN DEFAULT TRUE,
  visible_in_detail BOOLEAN DEFAULT TRUE,
  visible_in_form BOOLEAN DEFAULT TRUE,
  visible_in_gantt BOOLEAN DEFAULT FALSE,
  placeholder TEXT DEFAULT '',
  default_value TEXT DEFAULT '',
  sort_order INTEGER DEFAULT 0,
  enabled BOOLEAN DEFAULT TRUE,
  is_enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
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
  enabled BOOLEAN DEFAULT TRUE,
  is_enabled BOOLEAN DEFAULT TRUE,
  is_system BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(group_key, option_value)
);

CREATE TABLE IF NOT EXISTS audit_project_field_values (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES audit_projects(id) ON DELETE CASCADE,
  field_key TEXT NOT NULL,
  field_value TEXT DEFAULT '',
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(project_id, field_key)
);

CREATE TABLE IF NOT EXISTS audit_stage_field_values (
  id TEXT PRIMARY KEY,
  stage_id TEXT NOT NULL REFERENCES audit_project_stages(id) ON DELETE CASCADE,
  project_id TEXT DEFAULT '',
  field_key TEXT NOT NULL,
  field_value TEXT DEFAULT '',
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE(stage_id, field_key)
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
  contract_amount NUMERIC DEFAULT 0,
  submitted_amount NUMERIC DEFAULT 0,
  paid_amount NUMERIC DEFAULT 0,
  payment_terms TEXT DEFAULT '',
  planned_start_date TEXT DEFAULT '',
  planned_end_date TEXT DEFAULT '',
  description TEXT DEFAULT '',
  document_completion NUMERIC DEFAULT 0,
  missing_required_count INTEGER DEFAULT 0,
  settlement_book_status TEXT DEFAULT 'missing',
  first_audit_material_status TEXT DEFAULT 'missing',
  second_audit_material_status TEXT DEFAULT 'missing',
  variation_count INTEGER DEFAULT 0,
  variation_amount NUMERIC DEFAULT 0,
  audit_project_id TEXT DEFAULT '',
  created_by TEXT DEFAULT '',
  updated_by TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  deleted_at TIMESTAMPTZ,
  is_deleted BOOLEAN DEFAULT FALSE
);

-- Phase 1 document evidence graph.
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  document_type TEXT NOT NULL,
  lifecycle_stage TEXT NOT NULL,
  project_id TEXT REFERENCES project_records(id),
  candidate_project_id TEXT REFERENCES project_records(id),
  status TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'user_upload',
  current_version_id TEXT,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  version_no INTEGER NOT NULL,
  original_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  file_size BIGINT NOT NULL,
  sha256 TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  replaced_version_id TEXT REFERENCES document_versions(id),
  uploaded_by TEXT NOT NULL,
  uploaded_at TIMESTAMPTZ NOT NULL,
  UNIQUE (document_id, version_no)
);

CREATE TABLE IF NOT EXISTS document_pages (
  id TEXT PRIMARY KEY,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  page_number INTEGER NOT NULL,
  relative_path TEXT NOT NULL,
  width_px INTEGER NOT NULL,
  height_px INTEGER NOT NULL,
  dpi INTEGER NOT NULL DEFAULT 300,
  rotation_degrees INTEGER NOT NULL DEFAULT 0,
  quality_score DOUBLE PRECISION,
  preprocessing_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (document_version_id, page_number)
);

CREATE TABLE IF NOT EXISTS recognition_jobs (
  id TEXT PRIMARY KEY,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  adapter_key TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  model_version TEXT DEFAULT '',
  provider_request_id TEXT DEFAULT '',
  idempotency_key TEXT NOT NULL UNIQUE,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  lease_owner TEXT DEFAULT '',
  lease_expires_at TIMESTAMPTZ,
  next_attempt_at TIMESTAMPTZ,
  error_code TEXT DEFAULT '',
  error_message TEXT DEFAULT '',
  provider_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  source_recognition_job_id TEXT REFERENCES recognition_jobs(id),
  fallback_reason TEXT NOT NULL DEFAULT '',
  fallback_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS project_intake_drafts (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  document_id TEXT REFERENCES documents(id),
  document_version_id TEXT REFERENCES document_versions(id),
  schema_version TEXT NOT NULL DEFAULT 'contract.v1',
  values_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  fallback_reason TEXT NOT NULL DEFAULT '',
  fallback_note TEXT NOT NULL DEFAULT '',
  completed_project_id TEXT REFERENCES project_records(id),
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ocr_blocks (
  id TEXT PRIMARY KEY,
  recognition_job_id TEXT NOT NULL REFERENCES recognition_jobs(id) ON DELETE CASCADE,
  document_page_id TEXT NOT NULL REFERENCES document_pages(id) ON DELETE CASCADE,
  block_type TEXT NOT NULL,
  raw_text TEXT NOT NULL DEFAULT '',
  confidence DOUBLE PRECISION,
  bbox_json JSONB NOT NULL,
  row_index INTEGER,
  column_index INTEGER,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS extracted_fields (
  id TEXT PRIMARY KEY,
  recognition_job_id TEXT NOT NULL REFERENCES recognition_jobs(id) ON DELETE CASCADE,
  semantic_key TEXT NOT NULL,
  raw_value TEXT NOT NULL DEFAULT '',
  normalized_value_json JSONB NOT NULL DEFAULT 'null'::jsonb,
  confidence DOUBLE PRECISION,
  validation_status TEXT NOT NULL DEFAULT 'unvalidated',
  source_kind TEXT NOT NULL DEFAULT 'ocr',
  model_version TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (recognition_job_id, semantic_key)
);

CREATE TABLE IF NOT EXISTS evidence_anchors (
  id TEXT PRIMARY KEY,
  extracted_field_id TEXT NOT NULL REFERENCES extracted_fields(id) ON DELETE CASCADE,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  document_page_id TEXT NOT NULL REFERENCES document_pages(id) ON DELETE CASCADE,
  bbox_json JSONB NOT NULL,
  source_text TEXT NOT NULL DEFAULT '',
  image_crop_relative_path TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS document_reviews (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
  recognition_job_id TEXT NOT NULL REFERENCES recognition_jobs(id) ON DELETE CASCADE,
  project_id TEXT REFERENCES project_records(id),
  candidate_project_id TEXT REFERENCES project_records(id),
  status TEXT NOT NULL DEFAULT 'open',
  review_version INTEGER NOT NULL DEFAULT 0,
  blockers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  confirmation_idempotency_key TEXT UNIQUE,
  reviewer_id TEXT DEFAULT '',
  reviewer_name TEXT DEFAULT '',
  opened_at TIMESTAMPTZ NOT NULL,
  confirmed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (document_version_id, recognition_job_id)
);

CREATE TABLE IF NOT EXISTS review_decisions (
  id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL REFERENCES document_reviews(id) ON DELETE CASCADE,
  extracted_field_id TEXT NOT NULL REFERENCES extracted_fields(id) ON DELETE CASCADE,
  decision TEXT NOT NULL,
  ai_value_json JSONB NOT NULL DEFAULT 'null'::jsonb,
  confirmed_value_json JSONB NOT NULL DEFAULT 'null'::jsonb,
  reason TEXT DEFAULT '',
  reviewer_id TEXT NOT NULL,
  reviewer_name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  UNIQUE (review_id, extracted_field_id)
);

CREATE TABLE IF NOT EXISTS review_decision_history (
  id TEXT PRIMARY KEY,
  review_decision_id TEXT NOT NULL REFERENCES review_decisions(id) ON DELETE CASCADE,
  review_id TEXT NOT NULL REFERENCES document_reviews(id) ON DELETE CASCADE,
  extracted_field_id TEXT NOT NULL REFERENCES extracted_fields(id) ON DELETE CASCADE,
  decision TEXT NOT NULL,
  ai_value_json JSONB NOT NULL DEFAULT 'null'::jsonb,
  confirmed_value_json JSONB NOT NULL DEFAULT 'null'::jsonb,
  reason TEXT DEFAULT '',
  reviewer_id TEXT NOT NULL,
  reviewer_name TEXT NOT NULL,
  revision_no INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (review_decision_id, revision_no)
);

CREATE TABLE IF NOT EXISTS stage_form_snapshots (
  id TEXT PRIMARY KEY,
  review_id TEXT NOT NULL UNIQUE REFERENCES document_reviews(id),
  project_id TEXT NOT NULL REFERENCES project_records(id) ON DELETE CASCADE,
  stage_key TEXT NOT NULL,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id),
  form_template_version TEXT NOT NULL,
  extraction_schema_version TEXT NOT NULL,
  values_json JSONB NOT NULL,
  evidence_manifest_json JSONB NOT NULL,
  confirmed_by TEXT NOT NULL,
  confirmed_by_name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS project_lifecycle_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project_records(id) ON DELETE CASCADE,
  from_stage TEXT NOT NULL,
  to_stage TEXT NOT NULL,
  transition_type TEXT NOT NULL DEFAULT 'forward',
  reason TEXT DEFAULT '',
  idempotency_key TEXT NOT NULL,
  lifecycle_version INTEGER NOT NULL,
  actor_id TEXT DEFAULT '',
  actor_name TEXT DEFAULT '',
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  stage_form_snapshot_id TEXT REFERENCES stage_form_snapshots(id),
  evidence_document_version_id TEXT REFERENCES document_versions(id),
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE (project_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS project_contracts (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project_records(id) ON DELETE CASCADE,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id),
  stage_form_snapshot_id TEXT NOT NULL REFERENCES stage_form_snapshots(id),
  contract_name TEXT NOT NULL DEFAULT '',
  contract_number TEXT NOT NULL DEFAULT '',
  contract_type TEXT NOT NULL DEFAULT '',
  owner_unit TEXT NOT NULL,
  contractor_unit TEXT NOT NULL,
  project_manager TEXT NOT NULL DEFAULT '',
  contract_amount NUMERIC(18,4) NOT NULL,
  signed_date TEXT NOT NULL,
  start_date TEXT DEFAULT '',
  end_date TEXT DEFAULT '',
  payment_terms_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  retention_terms_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  performance_bond_terms_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_current BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS project_acceptance_records (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project_records(id) ON DELETE CASCADE,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id),
  stage_form_snapshot_id TEXT NOT NULL REFERENCES stage_form_snapshots(id),
  conclusion TEXT NOT NULL,
  acceptance_date TEXT NOT NULL,
  completion_date TEXT DEFAULT '',
  contractor_unit TEXT NOT NULL DEFAULT '',
  supervisor_unit TEXT NOT NULL DEFAULT '',
  designer_unit TEXT NOT NULL DEFAULT '',
  contract_amount_reference NUMERIC(18,4),
  signature_status_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS project_audit_determinations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project_records(id) ON DELETE CASCADE,
  document_version_id TEXT NOT NULL REFERENCES document_versions(id),
  stage_form_snapshot_id TEXT NOT NULL REFERENCES stage_form_snapshots(id),
  audit_type TEXT NOT NULL DEFAULT '',
  submitted_amount NUMERIC(18,4),
  first_determined_amount NUMERIC(18,4),
  second_determined_amount NUMERIC(18,4),
  engineering_determined_amount NUMERIC(18,4) NOT NULL,
  review_fee_deduction NUMERIC(18,4) NOT NULL DEFAULT 0,
  final_settlement_amount NUMERIC(18,4) NOT NULL,
  reduction_amount NUMERIC(18,4),
  reduction_rate NUMERIC(9,6),
  determination_date TEXT NOT NULL,
  uppercase_amount TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS system_users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  email TEXT DEFAULT '',
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer',
  is_active BOOLEAN DEFAULT TRUE,
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS system_settings (
  setting_key TEXT PRIMARY KEY,
  setting_value JSONB NOT NULL,
  setting_group TEXT DEFAULT 'system',
  description TEXT DEFAULT '',
  updated_by TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
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
  detail_json JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS system_theme_configs (
  id TEXT PRIMARY KEY,
  theme_key TEXT UNIQUE NOT NULL,
  theme_name TEXT NOT NULL,
  package_name TEXT NOT NULL,
  preview_colors JSONB DEFAULT '[]'::jsonb,
  apply_scope TEXT DEFAULT 'global',
  is_enabled BOOLEAN DEFAULT TRUE,
  is_default BOOLEAN DEFAULT FALSE,
  dark_mode_enabled BOOLEAN DEFAULT FALSE,
  compact_mode_enabled BOOLEAN DEFAULT FALSE,
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_projects_stage ON audit_projects(current_stage);
CREATE INDEX IF NOT EXISTS idx_audit_projects_updated ON audit_projects(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_attachments_project ON audit_project_attachments(project_id, is_deleted, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_field_configs_sort ON audit_field_configs(entity_type, sort_order);
CREATE INDEX IF NOT EXISTS idx_audit_field_options_group ON audit_field_options(group_key, sort_order);
CREATE INDEX IF NOT EXISTS idx_project_lifecycle_events_project ON project_lifecycle_events(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_project_type ON documents(project_id, document_type, status);
CREATE INDEX IF NOT EXISTS idx_document_versions_hash ON document_versions(sha256);
CREATE INDEX IF NOT EXISTS idx_document_pages_version ON document_pages(document_version_id, page_number);
CREATE INDEX IF NOT EXISTS idx_recognition_jobs_status ON recognition_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_project_intake_drafts_owner ON project_intake_drafts(owner_user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_intake_drafts_status ON project_intake_drafts(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_extracted_fields_job_key ON extracted_fields(recognition_job_id, semantic_key);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON document_reviews(status, opened_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_contracts_current ON project_contracts(project_id) WHERE is_current;
CREATE OR REPLACE FUNCTION reject_stage_form_snapshot_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'stage form snapshots are immutable';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_stage_form_snapshots_immutable_update ON stage_form_snapshots;
CREATE TRIGGER trg_stage_form_snapshots_immutable_update
BEFORE UPDATE ON stage_form_snapshots
FOR EACH ROW EXECUTE FUNCTION reject_stage_form_snapshot_mutation();
DROP TRIGGER IF EXISTS trg_stage_form_snapshots_immutable_delete ON stage_form_snapshots;
CREATE TRIGGER trg_stage_form_snapshots_immutable_delete
BEFORE DELETE ON stage_form_snapshots
FOR EACH ROW EXECUTE FUNCTION reject_stage_form_snapshot_mutation();
CREATE OR REPLACE FUNCTION reject_duplicate_contract_document()
RETURNS trigger AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM project_contracts existing_contract
    JOIN document_versions existing_version
      ON existing_version.id = existing_contract.document_version_id
    JOIN document_versions new_version
      ON new_version.id = NEW.document_version_id
    WHERE existing_version.sha256 = new_version.sha256
  ) THEN
    RAISE EXCEPTION 'contract document already created a project';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_project_contract_document_unique ON project_contracts;
CREATE TRIGGER trg_project_contract_document_unique
BEFORE INSERT ON project_contracts
FOR EACH ROW EXECUTE FUNCTION reject_duplicate_contract_document();
CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_operation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_users_username ON system_users(username);
