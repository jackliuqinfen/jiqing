import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import audit_api
from server.migrations import (
    CONTRACT_FALLBACK_MIGRATION,
    DOCUMENT_CONFIRMATION_GUARDS_MIGRATION,
    DOCUMENT_EVIDENCE_CHECKSUM,
    DOCUMENT_EVIDENCE_MIGRATION,
    LIFECYCLE_RUNTIME_MIGRATION,
    MigrationChecksumMismatchError,
    apply_pending_migrations,
)


EXPECTED_TABLES = {
    "documents",
    "document_versions",
    "document_pages",
    "recognition_jobs",
    "ocr_blocks",
    "extracted_fields",
    "evidence_anchors",
    "document_reviews",
    "review_decisions",
    "review_decision_history",
    "stage_form_snapshots",
    "project_contracts",
    "project_acceptance_records",
    "project_audit_determinations",
    "project_intake_drafts",
}


class DocumentMigrationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute(
            """
            CREATE TABLE project_records (
              id TEXT PRIMARY KEY,
              project_status TEXT DEFAULT 'awarded',
              lifecycle_version INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_document_migration_creates_complete_evidence_schema(self):
        apply_pending_migrations(self.conn)

        tables = {
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(EXPECTED_TABLES.issubset(tables))

        event_columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(project_lifecycle_events)")
        }
        self.assertIn("stage_form_snapshot_id", event_columns)
        self.assertIn("evidence_document_version_id", event_columns)

    def test_bootstrap_runs_versioned_migrations_before_canonical_schema(self):
        original_path = os.environ.get("AUDIT_DB_PATH")
        with tempfile.TemporaryDirectory() as tempdir:
            os.environ["AUDIT_DB_PATH"] = str(Path(tempdir) / "bootstrap.sqlite3")
            observed = []
            real_apply = apply_pending_migrations

            def assert_before_schema(conn):
                observed.append(
                    conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'documents'"
                    ).fetchone()
                )
                real_apply(conn)

            try:
                with patch.object(audit_api, "apply_pending_migrations", assert_before_schema):
                    audit_api.bootstrap()
            finally:
                if original_path is None:
                    os.environ.pop("AUDIT_DB_PATH", None)
                else:
                    os.environ["AUDIT_DB_PATH"] = original_path

        self.assertEqual(observed, [None])

    def test_canonical_schema_cold_start_has_no_foreign_key_errors(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            apply_pending_migrations(conn)
            schema = (
                Path(__file__).resolve().parents[1] / "schema.sql"
            ).read_text(encoding="utf-8")
            conn.executescript(schema)

            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()

    def test_migrations_are_ordered_idempotent_and_recorded_once(self):
        apply_pending_migrations(self.conn)
        apply_pending_migrations(self.conn)

        rows = self.conn.execute(
            "SELECT version, success FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual(
            [(row["version"], row["success"]) for row in rows],
            [
                (LIFECYCLE_RUNTIME_MIGRATION, 1),
                (DOCUMENT_EVIDENCE_MIGRATION, 1),
                (DOCUMENT_CONFIRMATION_GUARDS_MIGRATION, 1),
                (CONTRACT_FALLBACK_MIGRATION, 1),
            ],
        )

    def test_contract_fallback_migration_adds_drafts_and_job_provenance(self):
        apply_pending_migrations(self.conn)

        draft_columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(project_intake_drafts)")
        }
        self.assertTrue(
            {
                "owner_user_id",
                "status",
                "document_id",
                "document_version_id",
                "schema_version",
                "values_json",
                "fallback_reason",
                "fallback_note",
                "completed_project_id",
            }.issubset(draft_columns)
        )
        recognition_columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(recognition_jobs)")
        }
        self.assertIn("source_recognition_job_id", recognition_columns)

        indexes = {
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        self.assertIn("idx_project_intake_drafts_owner", indexes)
        self.assertIn("idx_project_intake_drafts_status", indexes)

        self._insert_version()
        now = "2026-07-15T00:00:00Z"
        self.conn.execute(
            """
            INSERT INTO recognition_jobs
            (id, document_version_id, status, adapter_key, schema_version,
             idempotency_key, created_at, updated_at)
            VALUES ('source-job', 'version-1', 'failed', 'volcengine',
                    'contract.v1', 'source-key', ?, ?)
            """,
            (now, now),
        )
        self.conn.execute(
            """
            INSERT INTO recognition_jobs
            (id, document_version_id, status, adapter_key, schema_version,
             idempotency_key, source_recognition_job_id, created_at, updated_at)
            VALUES ('fallback-job', 'version-1', 'review_ready', 'manual-entry',
                    'contract.v1', 'fallback-key', 'source-job', ?, ?)
            """,
            (now, now),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE recognition_jobs SET source_recognition_job_id = 'missing' "
                "WHERE id = 'fallback-job'"
            )

    def test_document_version_number_is_unique_within_document(self):
        apply_pending_migrations(self.conn)
        self.conn.execute(
            """
            INSERT INTO documents
            (id, document_type, lifecycle_stage, status, source, created_by, created_at, updated_at)
            VALUES ('doc-1', 'construction_contract', 'contract_handoff', 'uploaded',
                    'user_upload', 'user-1', '2026-07-13T00:00:00Z', '2026-07-13T00:00:00Z')
            """
        )
        values = (
            "version-1",
            "doc-1",
            1,
            "contract.pdf",
            "application/pdf",
            10,
            "abc",
            "documents/doc-1/v1/original/contract.pdf",
            "user-1",
            "2026-07-13T00:00:00Z",
        )
        self.conn.execute(
            """
            INSERT INTO document_versions
            (id, document_id, version_no, original_name, mime_type, file_size, sha256,
             relative_path, uploaded_by, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO document_versions
                (id, document_id, version_no, original_name, mime_type, file_size, sha256,
                 relative_path, uploaded_by, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("version-2", *values[1:]),
            )

    def test_evidence_foreign_keys_are_enabled_by_schema(self):
        apply_pending_migrations(self.conn)

        foreign_keys = {
            (row["table"], row["from"], row["to"])
            for row in self.conn.execute("PRAGMA foreign_key_list(document_versions)")
        }

        self.assertIn(("documents", "document_id", "id"), foreign_keys)

    def test_lifecycle_event_rejects_missing_evidence_references_on_insert(self):
        apply_pending_migrations(self.conn)
        self.conn.execute("INSERT INTO project_records (id) VALUES ('project-1')")

        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_lifecycle_event(
                event_id="event-1",
                idempotency_key="transition-1",
                stage_form_snapshot_id="missing-snapshot",
            )

    def test_lifecycle_event_rejects_missing_evidence_references_on_update(self):
        apply_pending_migrations(self.conn)
        self.conn.execute("INSERT INTO project_records (id) VALUES ('project-1')")
        self._insert_lifecycle_event(
            event_id="event-1",
            idempotency_key="transition-1",
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                UPDATE project_lifecycle_events
                SET evidence_document_version_id = 'missing-version'
                WHERE id = 'event-1'
                """
            )

    def test_document_checksum_mismatch_is_rejected_without_rewriting_history(self):
        apply_pending_migrations(self.conn)
        self.conn.execute(
            "UPDATE schema_migrations SET checksum = 'changed' WHERE version = ?",
            (DOCUMENT_EVIDENCE_MIGRATION,),
        )
        self.conn.commit()

        with self.assertRaises(MigrationChecksumMismatchError):
            apply_pending_migrations(self.conn)

        row = self.conn.execute(
            "SELECT checksum, success FROM schema_migrations WHERE version = ?",
            (DOCUMENT_EVIDENCE_MIGRATION,),
        ).fetchone()
        self.assertEqual(row["checksum"], "changed")
        self.assertEqual(row["success"], 1)

    def test_document_ddl_failure_rolls_back_and_records_failed_migration(self):
        self.conn.execute("CREATE VIEW documents AS SELECT 'blocked' AS id")
        self.conn.commit()

        with self.assertRaises(sqlite3.OperationalError):
            apply_pending_migrations(self.conn)

        lifecycle = self.conn.execute(
            "SELECT success FROM schema_migrations WHERE version = ?",
            (LIFECYCLE_RUNTIME_MIGRATION,),
        ).fetchone()
        evidence = self.conn.execute(
            "SELECT checksum, success FROM schema_migrations WHERE version = ?",
            (DOCUMENT_EVIDENCE_MIGRATION,),
        ).fetchone()
        self.assertEqual(lifecycle["success"], 1)
        self.assertEqual(evidence["checksum"], DOCUMENT_EVIDENCE_CHECKSUM)
        self.assertEqual(evidence["success"], 0)
        self.assertNotIn(
            "document_versions",
            {
                row["name"]
                for row in self.conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            },
        )

    def test_recognition_idempotency_key_is_globally_unique(self):
        apply_pending_migrations(self.conn)
        self._insert_version()
        values = (
            "job-1",
            "version-1",
            "queued",
            "http-layout-v1",
            "contract.v1",
            "recognize:version-1:contract.v1",
            "2026-07-13T00:00:00Z",
            "2026-07-13T00:00:00Z",
        )
        self.conn.execute(
            """
            INSERT INTO recognition_jobs
            (id, document_version_id, status, adapter_key, schema_version,
             idempotency_key, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO recognition_jobs
                (id, document_version_id, status, adapter_key, schema_version,
                 idempotency_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("job-2", *values[1:]),
            )

    def test_money_facts_use_integer_fen_columns(self):
        apply_pending_migrations(self.conn)
        contract_columns = {
            row["name"]: row["type"]
            for row in self.conn.execute("PRAGMA table_info(project_contracts)")
        }
        determination_columns = {
            row["name"]: row["type"]
            for row in self.conn.execute(
                "PRAGMA table_info(project_audit_determinations)"
            )
        }
        self.assertEqual(contract_columns["contract_amount_fen"], "INTEGER")
        self.assertEqual(
            determination_columns["engineering_determined_amount_fen"], "INTEGER"
        )
        self.assertEqual(
            determination_columns["final_settlement_amount_fen"], "INTEGER"
        )

    def test_postgres_schema_constrains_project_and_event_evidence_references(self):
        schema = (
            Path(__file__).resolve().parents[1] / "postgres_schema.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS project_records", schema)
        self.assertIn(
            "project_id TEXT NOT NULL REFERENCES project_records(id) ON DELETE CASCADE",
            schema,
        )
        self.assertIn(
            "stage_form_snapshot_id TEXT REFERENCES stage_form_snapshots(id)",
            schema,
        )
        self.assertIn(
            "evidence_document_version_id TEXT REFERENCES document_versions(id)",
            schema,
        )

    def _insert_version(self):
        self.conn.execute(
            """
            INSERT INTO documents
            (id, document_type, lifecycle_stage, status, source, created_by, created_at, updated_at)
            VALUES ('doc-1', 'construction_contract', 'contract_handoff', 'uploaded',
                    'user_upload', 'user-1', '2026-07-13T00:00:00Z', '2026-07-13T00:00:00Z')
            """
        )
        self.conn.execute(
            """
            INSERT INTO document_versions
            (id, document_id, version_no, original_name, mime_type, file_size, sha256,
             relative_path, uploaded_by, uploaded_at)
            VALUES ('version-1', 'doc-1', 1, 'contract.pdf', 'application/pdf', 10,
                    'abc', 'documents/doc-1/v1/original/contract.pdf', 'user-1',
                    '2026-07-13T00:00:00Z')
            """
        )

    def _insert_lifecycle_event(
        self,
        *,
        event_id,
        idempotency_key,
        stage_form_snapshot_id=None,
        evidence_document_version_id=None,
    ):
        self.conn.execute(
            """
            INSERT INTO project_lifecycle_events
            (id, project_id, from_stage, to_stage, idempotency_key,
             lifecycle_version, stage_form_snapshot_id,
             evidence_document_version_id, created_at)
            VALUES (?, 'project-1', 'contract_handoff', 'site_entry', ?, 1, ?, ?,
                    '2026-07-13T00:00:00Z')
            """,
            (
                event_id,
                idempotency_key,
                stage_form_snapshot_id,
                evidence_document_version_id,
            ),
        )


if __name__ == "__main__":
    unittest.main()
