import sqlite3
import unittest

from server.document_repository import create_document_upload
from server.migrations import apply_pending_migrations
from server.project_intake_drafts import (
    ProjectIntakeDraftError,
    abandon_draft,
    create_draft,
    get_draft,
    list_drafts,
    save_draft,
)


NOW = "2026-07-15T03:00:00Z"


def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE project_records (
          id TEXT PRIMARY KEY,
          project_status TEXT DEFAULT 'awarded',
          lifecycle_version INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    apply_pending_migrations(conn)
    return conn


class ProjectIntakeDraftTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_conn()

    def tearDown(self):
        self.conn.close()

    def test_drafts_are_owner_scoped_and_do_not_create_projects(self):
        mine = create_draft(
            self.conn,
            owner_user_id="editor-1",
            values={"project.name": "悦铂特项目"},
            fallback_reason="upload_failed",
            now=NOW,
        )
        create_draft(
            self.conn,
            owner_user_id="editor-2",
            values={"project.name": "其他项目"},
            fallback_reason="manual",
            now=NOW,
        )

        self.assertEqual([item["id"] for item in list_drafts(self.conn, owner_user_id="editor-1")], [mine["id"]])
        self.assertEqual(get_draft(self.conn, mine["id"], owner_user_id="editor-1")["values"]["project.name"], "悦铂特项目")
        self.assertIsNone(get_draft(self.conn, mine["id"], owner_user_id="editor-2"))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0], 0)

    def test_draft_values_are_limited_to_contract_schema(self):
        with self.assertRaisesRegex(ProjectIntakeDraftError, "不支持的合同字段"):
            create_draft(
                self.conn,
                owner_user_id="editor-1",
                values={"project.fake": "不能保存"},
                fallback_reason="manual",
                now=NOW,
            )

    def test_complete_manual_intake_state_round_trips_with_default_revision(self):
        project_values = {
            "contractorName": "徐华",
            "contractorContact": "13800000000",
            "companyRole": "施工单位",
            "settlementStatus": "not_started",
            "submittedAmount": 0,
            "paidAmount": 0,
            "paymentTerms": "验收合格后付至80%",
            "plannedStartDate": "2026-01-05",
            "plannedEndDate": "2026-02-03",
            "description": "维修项目",
        }
        ui_state = {
            "wizardStep": 1,
            "pdfPage": 28,
            "pdfScale": 1.1,
            "previewCollapsed": False,
        }

        draft = create_draft(
            self.conn,
            owner_user_id="editor-1",
            values={"project.name": "大洋湾小瀛台翻新改造项目"},
            project_values=project_values,
            ui_state=ui_state,
            fallback_reason="manual_selected",
            now=NOW,
        )

        self.assertEqual(draft["project_values"], project_values)
        self.assertEqual(draft["ui_state"], ui_state)
        self.assertEqual(draft["revision"], 0)

    def test_manual_intake_state_defaults_are_stable(self):
        draft = create_draft(
            self.conn,
            owner_user_id="editor-1",
            values={},
            fallback_reason="manual_selected",
            now=NOW,
        )

        self.assertEqual(draft["project_values"], {})
        self.assertEqual(
            draft["ui_state"],
            {
                "wizardStep": 0,
                "pdfPage": 1,
                "pdfScale": 1,
                "previewCollapsed": False,
            },
        )
        self.assertEqual(draft["revision"], 0)

    def test_manual_intake_state_rejects_unknown_and_invalid_values(self):
        invalid_states = (
            ({"unknown": "value"}, None),
            ({"submittedAmount": True}, None),
            ({"paidAmount": float("inf")}, None),
            (None, {"unknown": "value"}),
            (None, {"wizardStep": True}),
            (None, {"wizardStep": -1}),
            (None, {"wizardStep": 4}),
            (None, {"pdfPage": True}),
            (None, {"pdfPage": 0}),
            (None, {"pdfScale": True}),
            (None, {"pdfScale": float("nan")}),
            (None, {"pdfScale": 0.49}),
            (None, {"pdfScale": 2.51}),
            (None, {"previewCollapsed": 1}),
        )

        for project_values, ui_state in invalid_states:
            with self.subTest(project_values=project_values, ui_state=ui_state):
                with self.assertRaises(ProjectIntakeDraftError):
                    create_draft(
                        self.conn,
                        owner_user_id="editor-1",
                        values={},
                        project_values=project_values,
                        ui_state=ui_state,
                        fallback_reason="manual_selected",
                        now=NOW,
                    )

    def test_save_draft_uses_revision_compare_and_swap(self):
        draft = create_draft(
            self.conn,
            owner_user_id="editor-1",
            values={},
            fallback_reason="manual_selected",
            now=NOW,
        )

        updated = save_draft(
            self.conn,
            draft_id=draft["id"],
            owner_user_id="editor-1",
            expected_revision=0,
            project_values={"description": "第一次保存"},
            ui_state={"wizardStep": 1, "pdfPage": 2},
            now=NOW,
        )

        self.assertEqual(updated["revision"], 1)
        self.assertEqual(updated["project_values"]["description"], "第一次保存")
        self.assertEqual(updated["ui_state"]["pdfPage"], 2)
        with self.assertRaisesRegex(ProjectIntakeDraftError, "其他窗口更新") as raised:
            save_draft(
                self.conn,
                draft_id=draft["id"],
                owner_user_id="editor-1",
                expected_revision=0,
                project_values={"description": "过期写入"},
                now=NOW,
            )
        self.assertEqual(raised.exception.code, "draft_version_conflict")

    def test_document_and_version_must_match_before_draft_becomes_attached(self):
        first = create_document_upload(
            self.conn,
            document_type="construction_contract",
            lifecycle_stage="contract_handoff",
            project_id=None,
            original_name="合同1.pdf",
            mime_type="application/pdf",
            file_size=100,
            sha256="draft-hash-1",
            relative_path="documents/draft/1.pdf",
            uploaded_by="editor-1",
            now=NOW,
        )
        second = create_document_upload(
            self.conn,
            document_type="construction_contract",
            lifecycle_stage="contract_handoff",
            project_id=None,
            original_name="合同2.pdf",
            mime_type="application/pdf",
            file_size=100,
            sha256="draft-hash-2",
            relative_path="documents/draft/2.pdf",
            uploaded_by="editor-1",
            now=NOW,
        )
        draft = create_draft(
            self.conn,
            owner_user_id="editor-1",
            values={},
            fallback_reason="manual",
            now=NOW,
        )

        with self.assertRaisesRegex(ProjectIntakeDraftError, "文档版本"):
            save_draft(
                self.conn,
                draft_id=draft["id"],
                owner_user_id="editor-1",
                expected_revision=draft["revision"],
                document_id=first["document"]["id"],
                document_version_id=second["version"]["id"],
                now=NOW,
            )

        attached = save_draft(
            self.conn,
            draft_id=draft["id"],
            owner_user_id="editor-1",
            expected_revision=draft["revision"],
            document_id=first["document"]["id"],
            document_version_id=first["version"]["id"],
            now=NOW,
        )
        self.assertEqual(attached["status"], "document_attached")

    def test_abandoned_draft_is_immutable(self):
        draft = create_draft(
            self.conn,
            owner_user_id="editor-1",
            values={"project.name": "悦铂特项目"},
            fallback_reason="manual",
            now=NOW,
        )
        abandoned = abandon_draft(
            self.conn,
            draft_id=draft["id"],
            owner_user_id="editor-1",
            now=NOW,
        )
        self.assertEqual(abandoned["status"], "abandoned")
        with self.assertRaisesRegex(ProjectIntakeDraftError, "不能继续修改"):
            save_draft(
                self.conn,
                draft_id=draft["id"],
                owner_user_id="editor-1",
                expected_revision=abandoned["revision"],
                values={"project.name": "修改"},
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
