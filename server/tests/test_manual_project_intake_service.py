import json
import sqlite3
import unittest
from pathlib import Path

from server.document_repository import create_document_upload
from server.manual_project_intake_service import (
    ManualProjectIntakeError,
    confirm_manual_project_intake,
)
from server.project_intake_drafts import create_draft
from server.document_review_service import ReviewBlockedError


NOW = "2026-08-13T02:00:00Z"
ACTOR = {"id": "editor-1", "name": "录入员", "role": "editor"}

CONTRACT_VALUES = {
    "project.name": "大洋湾小瀛台翻新改造项目",
    "party.owner": "盐城大洋湾组团开发有限公司",
    "party.contractor": "盐城太悦装配建筑工程有限公司",
    "contract.amount": 26_505_729,
    "contract.signed_date": "2026-02-03",
    "contract.start_date": "2026-01-05",
    "contract.end_date": "2026-02-03",
    "project.manager": "徐华",
    "contract.payment_terms": [
        "全部工程完成且验收合格后付至已完成工程量价款的80%",
        "竣工结算完成后支付至审定价款的97%",
        "余款为质保金，质保期两年后结清",
    ],
}

PROJECT_VALUES = {
    "contractorName": "徐华",
    "contractorContact": "",
    "companyRole": "施工单位",
    "settlementStatus": "not_started",
    "submittedAmount": 0,
    "paidAmount": 123.45,
    "paymentTerms": "全部工程完成且验收合格后付至80%\n竣工结算后付至97%\n余款质保两年",
    "plannedStartDate": "2026-01-05",
    "plannedEndDate": "2026-02-03",
    "description": "维修项目",
}


def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema = Path(__file__).resolve().parents[1] / "schema.sql"
    conn.executescript(schema.read_text(encoding="utf-8"))
    conn.execute(
        """
        INSERT INTO project_document_categories
        (id, category_key, category_name, required, required_from_stage,
         sort_order, enabled, created_at, updated_at)
        VALUES ('category-contract', 'contract', '施工合同', 1,
                'contract_signed', 1, 1, ?, ?)
        """,
        (NOW, NOW),
    )
    conn.commit()
    return conn


class ManualProjectIntakeServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_conn()

    def tearDown(self):
        self.conn.close()

    def upload_and_draft(self, *, suffix="main", mime_type="application/pdf", sha256=None):
        upload = create_document_upload(
            self.conn,
            document_type="construction_contract",
            lifecycle_stage="contract_handoff",
            project_id=None,
            original_name=f"大洋湾施工合同-{suffix}.pdf",
            mime_type=mime_type,
            file_size=4096,
            sha256=sha256 or f"manual-contract-{suffix}",
            relative_path=f"documents/manual/{suffix}.pdf",
            uploaded_by=ACTOR["id"],
            now=NOW,
        )
        draft = create_draft(
            self.conn,
            owner_user_id=ACTOR["id"],
            values=CONTRACT_VALUES,
            project_values=PROJECT_VALUES,
            fallback_reason="manual_selected",
            document_id=upload["document"]["id"],
            document_version_id=upload["version"]["id"],
            now=NOW,
        )
        self.conn.commit()
        return upload, draft

    def confirm(self, upload, draft, *, key="manual-project:main", logger=None, **changes):
        kwargs = {
            "document_version_id": upload["version"]["id"],
            "contract_values": CONTRACT_VALUES,
            "project_values": PROJECT_VALUES,
            "draft_id": draft["id"],
            "expected_draft_revision": draft["revision"],
            "idempotency_key": key,
            "form_template_version": "manual-project-wizard.v1",
            "actor": ACTOR,
            "project_code_generator": lambda *_args: f"20260203-TY-{key[-4:]}",
            "operation_logger": logger or (lambda *_args, **_kwargs: None),
            "now": NOW,
        }
        kwargs.update(changes)
        return confirm_manual_project_intake(self.conn, **kwargs)

    def test_happy_path_creates_formal_facts_without_rendering_or_ocr(self):
        upload, draft = self.upload_and_draft()
        calls = []

        result = self.confirm(
            upload,
            draft,
            logger=lambda action, target_type, target_id, detail: calls.append(
                (action, target_type, target_id, detail)
            ),
        )

        self.assertFalse(result["replayed"])
        self.assertEqual(result["project"]["id"], result["projectId"])
        self.assertIn("太悦", result["project"]["construction_unit"])
        self.assertNotIn("大悦", result["project"]["construction_unit"])
        self.assertEqual(result["project"]["paid_amount"], 123.45)
        self.assertEqual(result["project"]["document_completion"], 100)
        self.assertEqual(result["project"]["missing_required_count"], 0)
        self.assertEqual(result["project"]["payment_terms"], PROJECT_VALUES["paymentTerms"])
        self.assertEqual(
            json.loads(result["contract"]["payment_terms_json"]),
            CONTRACT_VALUES["contract.payment_terms"],
        )
        self.assertEqual(
            json.loads(result["snapshot"]["values_json"])["contract.payment_terms"],
            CONTRACT_VALUES["contract.payment_terms"],
        )
        for table in (
            "project_records",
            "project_contracts",
            "stage_form_snapshots",
            "project_lifecycle_events",
            "project_files",
        ):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 1)
        project_file = self.conn.execute("SELECT * FROM project_files").fetchone()
        self.assertEqual(project_file["category_key"], "contract")
        self.assertEqual(project_file["relative_path"], upload["version"]["relative_path"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM document_pages").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ocr_blocks").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM evidence_anchors").fetchone()[0], 0)
        nonempty_fields = self.conn.execute(
            "SELECT COUNT(*) FROM extracted_fields WHERE normalized_value_json <> 'null'"
        ).fetchone()[0]
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0],
            nonempty_fields,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM extracted_fields WHERE source_kind <> 'manual'"
            ).fetchone()[0],
            0,
        )
        completed = self.conn.execute(
            "SELECT status, completed_project_id, revision FROM project_intake_drafts WHERE id = ?",
            (draft["id"],),
        ).fetchone()
        self.assertEqual((completed["status"], completed["completed_project_id"]), ("completed", result["projectId"]))
        self.assertEqual(completed["revision"], draft["revision"] + 1)
        self.assertEqual(calls[0][0:3], ("manual_project_intake.confirm", "project_record", result["projectId"]))

    def test_required_values_pdf_mime_and_project_whitelist_are_enforced(self):
        cases = [
            ("owner", {**CONTRACT_VALUES, "party.owner": "   "}, PROJECT_VALUES, "confirmed_value_required"),
            ("amount", {**CONTRACT_VALUES, "contract.amount": 0}, PROJECT_VALUES, "contract_amount_invalid"),
            ("negative", {**CONTRACT_VALUES, "contract.amount": -1}, PROJECT_VALUES, "contract_amount_invalid"),
            (
                "overflow",
                {**CONTRACT_VALUES, "contract.amount": 9_223_372_036_854_775_808},
                PROJECT_VALUES,
                "contract_amount_invalid",
            ),
            (
                "terms",
                {**CONTRACT_VALUES, "contract.payment_terms": []},
                {**PROJECT_VALUES, "paymentTerms": ""},
                "confirmed_value_required",
            ),
            (
                "project-key",
                CONTRACT_VALUES,
                {**PROJECT_VALUES, "projectStatus": "archived"},
                "project_field_invalid",
            ),
        ]
        for suffix, contract_values, project_values, code in cases:
            with self.subTest(suffix=suffix):
                upload, draft = self.upload_and_draft(suffix=suffix)
                with self.assertRaises(ManualProjectIntakeError) as raised:
                    self.confirm(
                        upload,
                        draft,
                        key=f"manual-project:{suffix}",
                        contract_values=contract_values,
                        project_values=project_values,
                    )
                self.assertEqual(raised.exception.code, code)

        upload, draft = self.upload_and_draft(suffix="mime", mime_type="application/octet-stream")
        with self.assertRaises(ManualProjectIntakeError) as raised:
            self.confirm(upload, draft, key="manual-project:mime")
        self.assertEqual(raised.exception.code, "contract_pdf_required")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0], 0)

    def test_same_key_replays_before_completed_draft_check_and_duplicate_hash_is_blocked(self):
        upload, draft = self.upload_and_draft(suffix="original", sha256="same-pdf")
        first = self.confirm(upload, draft, key="manual-project:stable")
        replay = self.confirm(upload, draft, key="manual-project:stable")
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["projectId"], first["projectId"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0], 1)

        duplicate_upload, duplicate_draft = self.upload_and_draft(
            suffix="duplicate", sha256="same-pdf"
        )
        with self.assertRaises(ReviewBlockedError) as raised:
            self.confirm(
                duplicate_upload,
                duplicate_draft,
                key="manual-project:different",
            )
        self.assertIn("duplicate_contract_document", {item["code"] for item in raised.exception.blockers})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0], 1)

    def test_stale_draft_revision_conflicts_without_writes(self):
        upload, draft = self.upload_and_draft(suffix="stale")
        with self.assertRaises(ManualProjectIntakeError) as raised:
            self.confirm(upload, draft, expected_draft_revision=draft["revision"] + 1)
        self.assertEqual(raised.exception.code, "draft_version_conflict")
        for table in ("project_records", "project_contracts", "document_reviews", "recognition_jobs"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_post_project_failure_rolls_back_every_write(self):
        upload, draft = self.upload_and_draft(suffix="rollback")

        def fail_after_project(*_args, **_kwargs):
            raise RuntimeError("injected operation-log failure")

        with self.assertRaisesRegex(RuntimeError, "injected"):
            self.confirm(upload, draft, key="manual-project:rollback", logger=fail_after_project)

        for table in (
            "project_records",
            "project_contracts",
            "project_files",
            "document_reviews",
            "recognition_jobs",
            "review_decisions",
            "stage_form_snapshots",
            "project_lifecycle_events",
        ):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
        persisted = self.conn.execute(
            "SELECT status, completed_project_id, revision FROM project_intake_drafts WHERE id = ?",
            (draft["id"],),
        ).fetchone()
        self.assertEqual((persisted["status"], persisted["completed_project_id"], persisted["revision"]), ("document_attached", None, 0))

    def test_preview_authorization_matches_download_boundary(self):
        audit_api = Path(__file__).resolve().parents[1] / "audit_api.py"
        full_source = audit_api.read_text(encoding="utf-8")
        source = full_source.split("    def preview_project_file", 1)[1].split(
            "    def download_project_file", 1
        )[0]
        self.assertIn("user = self.require_user(conn)", source)
        self.assertIn("self.source_project_allowed(conn, user, row[\"project_id\"])", source)


if __name__ == "__main__":
    unittest.main()
