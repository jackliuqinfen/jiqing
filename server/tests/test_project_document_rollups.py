import sqlite3
import unittest

from server.audit_api import refresh_project_rollups


class ProjectDocumentRollupTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE project_records (
              id TEXT PRIMARY KEY,
              project_status TEXT NOT NULL,
              document_completion REAL DEFAULT 0,
              missing_required_count INTEGER DEFAULT 0,
              variation_count INTEGER DEFAULT 0,
              variation_amount REAL DEFAULT 0,
              paid_amount REAL DEFAULT 0,
              updated_at TEXT DEFAULT ''
            );
            CREATE TABLE project_document_categories (
              category_key TEXT PRIMARY KEY,
              required INTEGER NOT NULL,
              required_from_stage TEXT NOT NULL,
              enabled INTEGER NOT NULL
            );
            CREATE TABLE project_files (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              category_key TEXT NOT NULL,
              is_current INTEGER NOT NULL,
              is_deleted INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE project_variations (
              project_id TEXT NOT NULL,
              amount REAL DEFAULT 0,
              is_deleted INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE project_settlements (
              project_id TEXT NOT NULL,
              paid_amount REAL DEFAULT 0,
              is_deleted INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.conn.execute(
            "INSERT INTO project_records (id, project_status) VALUES ('project-1', 'contract_signed')"
        )
        self.conn.executemany(
            """
            INSERT INTO project_document_categories
            (category_key, required, required_from_stage, enabled)
            VALUES (?, 1, ?, 1)
            """,
            [
                ("contract", "contract_signed"),
                ("drawing", "under_construction"),
                ("settlement_book", "pending_submission"),
                ("first_audit", "first_audit"),
                ("second_audit", "second_audit"),
            ],
        )

    def tearDown(self):
        self.conn.close()

    def test_rollup_counts_only_requirements_reached_by_current_stage(self):
        refresh_project_rollups(self.conn, "project-1")

        row = self.conn.execute(
            "SELECT document_completion, missing_required_count FROM project_records WHERE id = 'project-1'"
        ).fetchone()
        self.assertEqual(row["missing_required_count"], 1)
        self.assertEqual(row["document_completion"], 0)

    def test_rollup_recalculates_when_project_enters_a_later_stage(self):
        self.conn.execute(
            """
            INSERT INTO project_files
            (id, project_id, category_key, is_current, is_deleted)
            VALUES ('file-contract', 'project-1', 'contract', 1, 0)
            """
        )
        self.conn.execute(
            "UPDATE project_records SET project_status = 'first_audit' WHERE id = 'project-1'"
        )

        refresh_project_rollups(self.conn, "project-1")

        row = self.conn.execute(
            "SELECT document_completion, missing_required_count FROM project_records WHERE id = 'project-1'"
        ).fetchone()
        self.assertEqual(row["missing_required_count"], 3)
        self.assertEqual(row["document_completion"], 25)


if __name__ == "__main__":
    unittest.main()
