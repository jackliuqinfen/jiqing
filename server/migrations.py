"""SQLite schema migrations for the Shenjikanban server."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


LIFECYCLE_RUNTIME_MIGRATION = "2026071101_lifecycle_runtime"
DOCUMENT_EVIDENCE_MIGRATION = "2026071301_document_evidence_phase1"
DOCUMENT_CONFIRMATION_GUARDS_MIGRATION = "2026071401_document_confirmation_guards"
CONTRACT_FALLBACK_MIGRATION = "2026071501_contract_fallback"
CONTRACT_FALLBACK_PROVENANCE_MIGRATION = "2026071502_contract_fallback_provenance"


class MigrationChecksumMismatchError(RuntimeError):
    """Raised when an applied migration no longer matches its definition."""

    def __init__(self, version, recorded_checksum, expected_checksum):
        super().__init__(
            f"Migration checksum mismatch for {version}: "
            f"recorded {recorded_checksum!r}, expected {expected_checksum!r}"
        )
        self.version = version
        self.recorded_checksum = recorded_checksum
        self.expected_checksum = expected_checksum


_LIFECYCLE_VERSION_ALTER_SQL = """
ALTER TABLE project_records ADD COLUMN lifecycle_version INTEGER NOT NULL DEFAULT 0
"""

_STAGE_FORM_SNAPSHOT_ALTER_SQL = """
ALTER TABLE project_lifecycle_events ADD COLUMN stage_form_snapshot_id TEXT
"""

_EVIDENCE_DOCUMENT_VERSION_ALTER_SQL = """
ALTER TABLE project_lifecycle_events ADD COLUMN evidence_document_version_id TEXT
"""

_LIFECYCLE_EVENT_TABLE_SQL = """
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
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
  UNIQUE (project_id, idempotency_key)
)
"""

_LIFECYCLE_RUNTIME_STATEMENTS = (
    _LIFECYCLE_EVENT_TABLE_SQL,
    """
    CREATE INDEX IF NOT EXISTS idx_project_lifecycle_events_project
    ON project_lifecycle_events(project_id, created_at DESC)
    """,
)

_LIFECYCLE_RUNTIME_MIGRATION_DEFINITION = (
    _LIFECYCLE_VERSION_ALTER_SQL,
    *_LIFECYCLE_RUNTIME_STATEMENTS,
)

LIFECYCLE_RUNTIME_CHECKSUM = hashlib.sha256(
    "\n".join(
        statement.strip() for statement in _LIFECYCLE_RUNTIME_MIGRATION_DEFINITION
    ).encode("utf-8")
).hexdigest()


_DOCUMENT_EVIDENCE_STATEMENTS = (
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
      FOREIGN KEY (document_version_id) REFERENCES document_versions(id) ON DELETE CASCADE
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    """
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
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_documents_project_type ON documents(project_id, document_type, status)",
    "CREATE INDEX IF NOT EXISTS idx_document_versions_hash ON document_versions(sha256)",
    "CREATE INDEX IF NOT EXISTS idx_document_pages_version ON document_pages(document_version_id, page_number)",
    "CREATE INDEX IF NOT EXISTS idx_recognition_jobs_status ON recognition_jobs(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_extracted_fields_job_key ON extracted_fields(recognition_job_id, semantic_key)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_status ON document_reviews(status, opened_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_project_contracts_current ON project_contracts(project_id) WHERE is_current = 1",
    """
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
    END
    """,
    """
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
    END
    """,
)

_DOCUMENT_EVIDENCE_MIGRATION_DEFINITION = (
    _STAGE_FORM_SNAPSHOT_ALTER_SQL,
    _EVIDENCE_DOCUMENT_VERSION_ALTER_SQL,
    *_DOCUMENT_EVIDENCE_STATEMENTS,
)

DOCUMENT_EVIDENCE_CHECKSUM = hashlib.sha256(
    "\n".join(
        statement.strip() for statement in _DOCUMENT_EVIDENCE_MIGRATION_DEFINITION
    ).encode("utf-8")
).hexdigest()


_DOCUMENT_CONFIRMATION_GUARD_STATEMENTS = (
    """
    CREATE TRIGGER IF NOT EXISTS trg_stage_form_snapshots_immutable_update
    BEFORE UPDATE ON stage_form_snapshots
    BEGIN
      SELECT RAISE(ABORT, 'stage form snapshots are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_stage_form_snapshots_immutable_delete
    BEFORE DELETE ON stage_form_snapshots
    BEGIN
      SELECT RAISE(ABORT, 'stage form snapshots are immutable');
    END
    """,
    """
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
    END
    """,
)

DOCUMENT_CONFIRMATION_GUARDS_CHECKSUM = hashlib.sha256(
    "\n".join(
        statement.strip() for statement in _DOCUMENT_CONFIRMATION_GUARD_STATEMENTS
    ).encode("utf-8")
).hexdigest()


_RECOGNITION_SOURCE_JOB_ALTER_SQL = """
ALTER TABLE recognition_jobs ADD COLUMN source_recognition_job_id TEXT
REFERENCES recognition_jobs(id)
"""

_CONTRACT_FALLBACK_STATEMENTS = (
    """
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
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_intake_drafts_owner
    ON project_intake_drafts(owner_user_id, updated_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_project_intake_drafts_status
    ON project_intake_drafts(status, updated_at DESC)
    """,
)

_CONTRACT_FALLBACK_MIGRATION_DEFINITION = (
    _RECOGNITION_SOURCE_JOB_ALTER_SQL,
    *_CONTRACT_FALLBACK_STATEMENTS,
)

CONTRACT_FALLBACK_CHECKSUM = hashlib.sha256(
    "\n".join(
        statement.strip() for statement in _CONTRACT_FALLBACK_MIGRATION_DEFINITION
    ).encode("utf-8")
).hexdigest()


_RECOGNITION_FALLBACK_REASON_ALTER_SQL = """
ALTER TABLE recognition_jobs ADD COLUMN fallback_reason TEXT NOT NULL DEFAULT ''
"""

_RECOGNITION_FALLBACK_NOTE_ALTER_SQL = """
ALTER TABLE recognition_jobs ADD COLUMN fallback_note TEXT NOT NULL DEFAULT ''
"""

_CONTRACT_FALLBACK_PROVENANCE_DEFINITION = (
    _RECOGNITION_FALLBACK_REASON_ALTER_SQL,
    _RECOGNITION_FALLBACK_NOTE_ALTER_SQL,
)

CONTRACT_FALLBACK_PROVENANCE_CHECKSUM = hashlib.sha256(
    "\n".join(
        statement.strip() for statement in _CONTRACT_FALLBACK_PROVENANCE_DEFINITION
    ).encode("utf-8")
).hexdigest()


def apply_pending_migrations(conn):
    """Apply ordered SQLite migrations once and verify applied definitions."""
    _ensure_schema_migrations_table(conn)
    conn.commit()
    _apply_migration(
        conn,
        version=LIFECYCLE_RUNTIME_MIGRATION,
        checksum=LIFECYCLE_RUNTIME_CHECKSUM,
        statements=_LIFECYCLE_RUNTIME_STATEMENTS,
        prepare=_prepare_lifecycle_runtime,
    )
    _apply_migration(
        conn,
        version=DOCUMENT_EVIDENCE_MIGRATION,
        checksum=DOCUMENT_EVIDENCE_CHECKSUM,
        statements=_DOCUMENT_EVIDENCE_STATEMENTS,
        prepare=_prepare_document_evidence,
    )
    _apply_migration(
        conn,
        version=DOCUMENT_CONFIRMATION_GUARDS_MIGRATION,
        checksum=DOCUMENT_CONFIRMATION_GUARDS_CHECKSUM,
        statements=_DOCUMENT_CONFIRMATION_GUARD_STATEMENTS,
    )
    _apply_migration(
        conn,
        version=CONTRACT_FALLBACK_MIGRATION,
        checksum=CONTRACT_FALLBACK_CHECKSUM,
        statements=_CONTRACT_FALLBACK_STATEMENTS,
        prepare=_prepare_contract_fallback,
    )
    _apply_migration(
        conn,
        version=CONTRACT_FALLBACK_PROVENANCE_MIGRATION,
        checksum=CONTRACT_FALLBACK_PROVENANCE_CHECKSUM,
        statements=(),
        prepare=_prepare_contract_fallback_provenance,
    )


def _apply_migration(conn, *, version, checksum, statements, prepare=None):
    started_at = _now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT success, checksum FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if row and int(_value(row, "success", 0)) == 1:
            recorded_checksum = _value(row, "checksum", 1)
            if recorded_checksum != checksum:
                raise MigrationChecksumMismatchError(
                    version,
                    recorded_checksum,
                    checksum,
                )
            conn.commit()
            return

        if row:
            conn.execute(
                """
                UPDATE schema_migrations
                SET checksum = ?, started_at = ?, finished_at = '', success = 0
                WHERE version = ?
                """,
                (checksum, started_at, version),
            )
        else:
            conn.execute(
                """
                INSERT INTO schema_migrations
                (version, checksum, started_at, finished_at, success)
                VALUES (?, ?, ?, '', 0)
                """,
                (version, checksum, started_at),
            )
        if prepare:
            prepare(conn)
        for statement in statements:
            conn.execute(statement)
        conn.execute(
            """
            UPDATE schema_migrations
            SET checksum = ?, finished_at = ?, success = 1
            WHERE version = ?
            """,
            (checksum, _now_iso(), version),
        )
        conn.commit()
    except MigrationChecksumMismatchError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        _record_failed_migration(conn, version, checksum, started_at)
        raise


def _prepare_lifecycle_runtime(conn):
    if _table_exists(conn, "project_records") and not _column_exists(
        conn,
        "project_records",
        "lifecycle_version",
    ):
        conn.execute(_LIFECYCLE_VERSION_ALTER_SQL)


def _prepare_document_evidence(conn):
    if not _column_exists(
        conn,
        "project_lifecycle_events",
        "stage_form_snapshot_id",
    ):
        conn.execute(_STAGE_FORM_SNAPSHOT_ALTER_SQL)
    if not _column_exists(
        conn,
        "project_lifecycle_events",
        "evidence_document_version_id",
    ):
        conn.execute(_EVIDENCE_DOCUMENT_VERSION_ALTER_SQL)


def _prepare_contract_fallback(conn):
    if not _column_exists(
        conn,
        "recognition_jobs",
        "source_recognition_job_id",
    ):
        conn.execute(_RECOGNITION_SOURCE_JOB_ALTER_SQL)


def _prepare_contract_fallback_provenance(conn):
    if not _column_exists(conn, "recognition_jobs", "fallback_reason"):
        conn.execute(_RECOGNITION_FALLBACK_REASON_ALTER_SQL)
    if not _column_exists(conn, "recognition_jobs", "fallback_note"):
        conn.execute(_RECOGNITION_FALLBACK_NOTE_ALTER_SQL)


def _ensure_schema_migrations_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          checksum TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT DEFAULT '',
          success INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def _record_failed_migration(conn, version, checksum, started_at):
    try:
        cursor = conn.execute(
            """
            UPDATE schema_migrations
            SET checksum = ?, started_at = ?, finished_at = ?, success = 0
            WHERE version = ? AND success = 0
            """,
            (
                checksum,
                started_at,
                _now_iso(),
                version,
            ),
        )
        if cursor.rowcount == 0:
            row = conn.execute(
                "SELECT success FROM schema_migrations WHERE version = ?",
                (version,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO schema_migrations
                    (version, checksum, started_at, finished_at, success)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (
                        version,
                        checksum,
                        started_at,
                        _now_iso(),
                    ),
                )
        conn.commit()
    except Exception:
        conn.rollback()


def _table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _column_exists(conn, table_name, column_name):
    return any(
        _pragma_column_name(row) == column_name
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    )


def _pragma_column_name(row):
    if _row_has_key(row, "name"):
        return row["name"]
    return row[1]


def _row_has_key(row, key):
    return hasattr(row, "keys") and key in row.keys()


def _value(row, key, index):
    if _row_has_key(row, key):
        return row[key]
    return row[index]


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
