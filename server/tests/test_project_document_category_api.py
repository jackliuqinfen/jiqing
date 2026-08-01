import sqlite3
import unittest

from server.audit_api import Handler


class ProjectDocumentCategoryApiTests(unittest.TestCase):
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
              updated_at TEXT DEFAULT '',
              is_deleted INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE project_document_categories (
              id TEXT PRIMARY KEY,
              category_key TEXT UNIQUE NOT NULL,
              category_name TEXT NOT NULL,
              description TEXT DEFAULT '',
              required INTEGER NOT NULL,
              required_from_stage TEXT NOT NULL,
              sort_order INTEGER DEFAULT 0,
              enabled INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT DEFAULT ''
            );
            CREATE TABLE project_files (
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
            INSERT INTO project_records (id, project_status)
            VALUES ('project-1', 'contract_signed');
            INSERT INTO project_document_categories
              (id, category_key, category_name, required, required_from_stage)
            VALUES ('category-contract', 'contract', '合同文件', 1, 'contract_signed');
            """
        )
        self.responses = []
        self.handler = object.__new__(Handler)
        self.handler.require_role = lambda _conn, _roles: {"username": "admin"}
        self.handler.write_operation_log = lambda *_args, **_kwargs: None
        self.handler.respond = lambda status, payload: self.responses.append((status, payload))

    def tearDown(self):
        self.conn.close()

    def test_admin_can_change_start_stage_and_rollups_are_recalculated(self):
        self.handler.update_project_document_category(
            self.conn,
            "contract",
            {"required": True, "requiredFromStage": "first_audit"},
        )

        category = self.conn.execute(
            "SELECT required_from_stage FROM project_document_categories WHERE category_key = 'contract'"
        ).fetchone()
        project = self.conn.execute(
            "SELECT document_completion, missing_required_count FROM project_records WHERE id = 'project-1'"
        ).fetchone()
        self.assertEqual(category["required_from_stage"], "first_audit")
        self.assertEqual(project["missing_required_count"], 0)
        self.assertEqual(project["document_completion"], 100)
        self.assertEqual(self.responses[-1][0], 200)
        self.assertEqual(self.responses[-1][1]["data"]["requiredFromStage"], "first_audit")

    def test_invalid_start_stage_is_rejected_without_changing_configuration(self):
        self.handler.update_project_document_category(
            self.conn,
            "contract",
            {"required": True, "requiredFromStage": "future_unknown_stage"},
        )

        category = self.conn.execute(
            "SELECT required_from_stage FROM project_document_categories WHERE category_key = 'contract'"
        ).fetchone()
        self.assertEqual(category["required_from_stage"], "contract_signed")
        self.assertEqual(self.responses[-1][0], 400)


if __name__ == "__main__":
    unittest.main()
