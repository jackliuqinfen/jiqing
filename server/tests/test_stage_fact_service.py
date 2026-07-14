import json
import sqlite3
import unittest
from pathlib import Path

from server.document_repository import (
    add_document_pages,
    create_document_upload,
    create_recognition_job,
)
from server.document_review_service import (
    ReviewBlockedError,
    confirm_review,
    open_review,
    save_decisions,
)


NOW = "2026-07-14T02:00:00Z"
ACTOR = {"id": "reviewer-1", "name": "复核员"}


def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).resolve().parents[1] / "schema.sql"
    conn.executescript(schema.read_text(encoding="utf-8"))
    return conn


def insert_project(conn, project_id, status, lifecycle_version=0):
    conn.execute(
        """
        INSERT INTO project_records
        (id, project_code, project_name, construction_unit, owner_unit,
         project_status, lifecycle_version, created_at, updated_at)
        VALUES (?, ?, ?, '江苏悦铂特建设工程有限公司', '建设单位', ?, ?, ?, ?)
        """,
        (project_id, f"CODE-{project_id}", f"项目-{project_id}", status, lifecycle_version, NOW, NOW),
    )
    conn.commit()


def ready_review(
    conn,
    *,
    document_type,
    stage,
    schema_version,
    fields,
    project_id=None,
    upload_hash=None,
    job_key=None,
):
    identity = job_key or project_id or "new"
    upload = create_document_upload(
        conn,
        document_type=document_type,
        lifecycle_stage=stage,
        project_id=project_id,
        original_name=f"{document_type}.pdf",
        mime_type="application/pdf",
        file_size=2048,
        sha256=upload_hash or f"hash-{document_type}-{project_id or 'new'}",
        relative_path=f"documents/{document_type}.pdf",
        uploaded_by=ACTOR["id"],
        now=NOW,
    )
    page = add_document_pages(
        conn,
        document_version_id=upload["version"]["id"],
        pages=[{
            "id": f"page-{document_type}-{identity}",
            "page_number": 1,
            "relative_path": "documents/page.png",
            "width_px": 2480,
            "height_px": 3508,
            "dpi": 300,
            "quality_score": 0.95,
            "preprocessing_version": "render-v1",
        }],
        now=NOW,
    )[0]
    job = create_recognition_job(
        conn,
        document_version_id=upload["version"]["id"],
        adapter_key="test-v1",
        schema_version=schema_version,
        idempotency_key=job_key or f"recognize:{document_type}:{project_id or 'new'}",
        now=NOW,
    )
    conn.execute("UPDATE recognition_jobs SET status = 'review_ready' WHERE id = ?", (job["id"],))
    conn.execute("UPDATE documents SET status = 'review_ready' WHERE id = ?", (upload["document"]["id"],))
    for index, (key, value) in enumerate(fields.items(), start=1):
        field_id = f"field-{document_type}-{identity}-{index}"
        anchor_id = f"anchor-{document_type}-{identity}-{index}"
        conn.execute(
            """
            INSERT INTO extracted_fields
            (id, recognition_job_id, semantic_key, raw_value, normalized_value_json,
             confidence, validation_status, source_kind, model_version, created_at)
            VALUES (?, ?, ?, ?, ?, 0.96, 'valid', 'ocr', 'test-v1', ?)
            """,
            (field_id, job["id"], key, str(value), json.dumps(value, ensure_ascii=False), NOW),
        )
        conn.execute(
            """
            INSERT INTO evidence_anchors
            (id, extracted_field_id, document_version_id, document_page_id,
             bbox_json, source_text, image_crop_relative_path, created_at)
            VALUES (?, ?, ?, ?, '[0.1,0.1,0.2,0.05]', ?, '', ?)
            """,
            (anchor_id, field_id, upload["version"]["id"], page["id"], str(value), NOW),
        )
    conn.commit()
    detail = open_review(
        conn,
        document_id=upload["document"]["id"],
        recognition_job_id=job["id"],
        project_id=project_id,
        actor=ACTOR,
        allowed_project_ids=(() if project_id is None else (project_id,)),
        now=NOW,
    )
    for field in detail["fields"]:
        detail = save_decisions(
            conn,
            review_id=detail["id"],
            expected_review_version=detail["reviewVersion"],
            decisions=[{
                "fieldId": field["id"],
                "decision": "accepted",
                "confirmedValue": field["aiValue"],
            }],
            actor=ACTOR,
            now=NOW,
        )
    return detail


CONTRACT_FIELDS = {
    "project.name": "悦铂特项目",
    "party.owner": "建设单位",
    "party.contractor": "江苏悦铂特建设工程有限公司",
    "contract.number": "HT-2026-001",
    "contract.type": "施工总承包合同",
    "contract.amount": 100_000_000,
    "contract.signed_date": "2026-07-01",
    "contract.start_date": "2026-07-05",
    "contract.end_date": "2026-12-31",
    "project.manager": "张项目",
    "contract.payment_terms": ["竣工验收后支付60%"],
    "contract.retention_terms": ["质保金3%"],
    "contract.performance_bond_terms": [],
}


ACCEPTANCE_FIELDS = {
    "project.name": "项目-project-accept",
    "party.contractor": "江苏悦铂特建设工程有限公司",
    "party.supervisor": "监理单位",
    "party.designer": "设计单位",
    "project.completion_date": "2026-07-09",
    "acceptance.date": "2026-07-10",
    "acceptance.conclusion": "验收合格",
    "acceptance.signatures": ["建设单位", "施工单位", "监理单位"],
}


FINAL_FIELDS = {
    "project.name": "项目-project-final",
    "party.owner": "建设单位",
    "party.contractor": "江苏悦铂特建设工程有限公司",
    "audit.type": "工程审计",
    "audit.submitted_amount": 100_000_000,
    "audit.first_determined_amount": 95_000_000,
    "audit.second_determined_amount": 90_000_000,
    "audit.engineering_determined_amount": 90_000_000,
    "audit.review_fee_deduction": 1_000_000,
    "audit.final_settlement_amount": 89_000_000,
    "audit.reduction_amount": 10_000_000,
    "audit.reduction_rate": "0.1",
    "audit.determination_date": "2026-07-11",
    "audit.uppercase_amount": 89_000_000,
}


class StageFactServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_conn()

    def tearDown(self):
        self.conn.close()

    def test_contract_confirmation_atomically_creates_project_contract_snapshot_and_event(self):
        review = ready_review(
            self.conn,
            document_type="construction_contract",
            stage="contract_handoff",
            schema_version="contract.v1",
            fields=CONTRACT_FIELDS,
        )
        self.conn.execute(
            """
            CREATE TRIGGER reject_awarded_project
            BEFORE INSERT ON project_records
            WHEN NEW.project_status = 'awarded'
            BEGIN SELECT RAISE(ABORT, 'awarded project must not be persisted'); END
            """
        )

        result = confirm_review(
            self.conn,
            review_id=review["id"],
            expected_review_version=review["reviewVersion"],
            idempotency_key="confirm:contract:1",
            actor=ACTOR,
            allowed_project_ids=(),
            form_template_version="contract-form.v1",
            project_code_generator=lambda _conn, _date, _contractor: "20260701-YBT-001",
            now=NOW,
        )
        replay = confirm_review(
            self.conn,
            review_id=review["id"],
            expected_review_version=review["reviewVersion"],
            idempotency_key="confirm:contract:1",
            actor=ACTOR,
            allowed_project_ids=(),
            form_template_version="contract-form.v1",
            project_code_generator=lambda *_args: "SHOULD-NOT-BE-USED",
            now=NOW,
        )

        self.assertEqual(result["status"], "created")
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["snapshot"]["id"], result["snapshot"]["id"])
        project = self.conn.execute("SELECT * FROM project_records").fetchone()
        contract = self.conn.execute("SELECT * FROM project_contracts").fetchone()
        event = self.conn.execute("SELECT * FROM project_lifecycle_events").fetchone()
        self.assertEqual(project["project_status"], "contract_signed")
        self.assertEqual(project["project_code"], "20260701-YBT-001")
        self.assertEqual(contract["contract_amount_fen"], 100_000_000)
        self.assertEqual(contract["project_id"], project["id"])
        self.assertEqual((event["from_stage"], event["to_stage"]), ("contract_handoff", "contract_signed"))
        self.assertEqual(event["stage_form_snapshot_id"], result["snapshot"]["id"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_contracts").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE stage_form_snapshots SET values_json = '{}' WHERE id = ?",
                (result["snapshot"]["id"],),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "DELETE FROM stage_form_snapshots WHERE id = ?",
                (result["snapshot"]["id"],),
            )

    def test_same_contract_version_cannot_create_a_second_project(self):
        first = ready_review(
            self.conn,
            document_type="construction_contract",
            stage="contract_handoff",
            schema_version="contract.v1",
            fields=CONTRACT_FIELDS,
        )
        first_result = confirm_review(
            self.conn,
            review_id=first["id"],
            expected_review_version=first["reviewVersion"],
            idempotency_key="confirm:contract:original",
            actor=ACTOR,
            allowed_project_ids=(),
            form_template_version="contract-form.v1",
            project_code_generator=lambda *_args: "20260701-YBT-001",
            now=NOW,
        )
        second = ready_review(
            self.conn,
            document_type="construction_contract",
            stage="contract_handoff",
            schema_version="contract.v1",
            fields=CONTRACT_FIELDS,
            upload_hash="hash-construction_contract-new",
            job_key="recognize:contract:duplicate-file",
        )
        with self.assertRaises(ReviewBlockedError):
            confirm_review(
                self.conn,
                review_id=second["id"],
                expected_review_version=second["reviewVersion"],
                idempotency_key="confirm:contract:second-project",
                actor=ACTOR,
                allowed_project_ids=(),
                form_template_version="contract-form.v1",
                project_code_generator=lambda *_args: "20260701-YBT-002",
                now=NOW,
            )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0],
            1,
        )

    def test_acceptance_requires_correct_stage_and_passed_conclusion(self):
        insert_project(self.conn, "project-early", "contract_signed", 1)
        early = ready_review(
            self.conn,
            document_type="completion_acceptance_certificate",
            stage="completed_acceptance",
            schema_version="acceptance.v1",
            fields={**ACCEPTANCE_FIELDS, "project.name": "项目-project-early"},
            project_id="project-early",
        )
        with self.assertRaises(ReviewBlockedError):
            confirm_review(
                self.conn,
                review_id=early["id"],
                expected_review_version=early["reviewVersion"],
                idempotency_key="confirm:acceptance:early",
                actor=ACTOR,
                allowed_project_ids=("project-early",),
                form_template_version="acceptance-form.v1",
                now=NOW,
            )
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM stage_form_snapshots").fetchone()[0], 0)

        insert_project(self.conn, "project-failed", "under_construction", 2)
        failed = ready_review(
            self.conn,
            document_type="completion_acceptance_certificate",
            stage="completed_acceptance",
            schema_version="acceptance.v1",
            fields={
                **ACCEPTANCE_FIELDS,
                "project.name": "项目-project-failed",
                "acceptance.conclusion": "验收未通过",
            },
            project_id="project-failed",
        )
        with self.assertRaises(ReviewBlockedError):
            confirm_review(
                self.conn,
                review_id=failed["id"],
                expected_review_version=failed["reviewVersion"],
                idempotency_key="confirm:acceptance:failed",
                actor=ACTOR,
                allowed_project_ids=("project-failed",),
                form_template_version="acceptance-form.v1",
                now=NOW,
            )

    def test_passed_acceptance_writes_fact_snapshot_and_lifecycle_event(self):
        insert_project(self.conn, "project-accept", "under_construction", 2)
        review = ready_review(
            self.conn,
            document_type="completion_acceptance_certificate",
            stage="completed_acceptance",
            schema_version="acceptance.v1",
            fields=ACCEPTANCE_FIELDS,
            project_id="project-accept",
        )
        result = confirm_review(
            self.conn,
            review_id=review["id"],
            expected_review_version=review["reviewVersion"],
            idempotency_key="confirm:acceptance:1",
            actor=ACTOR,
            allowed_project_ids=("project-accept",),
            form_template_version="acceptance-form.v1",
            now=NOW,
        )

        fact = self.conn.execute("SELECT * FROM project_acceptance_records").fetchone()
        project = self.conn.execute("SELECT * FROM project_records WHERE id = 'project-accept'").fetchone()
        event = self.conn.execute("SELECT * FROM project_lifecycle_events").fetchone()
        self.assertEqual(fact["conclusion"], "验收合格")
        self.assertEqual(project["project_status"], "completed_acceptance")
        self.assertEqual(project["lifecycle_version"], 3)
        self.assertEqual(event["stage_form_snapshot_id"], result["snapshot"]["id"])

    def test_project_matching_uses_reviewer_confirmed_values_not_raw_ocr_values(self):
        insert_project(self.conn, "project-confirmed-values", "under_construction", 2)
        review = ready_review(
            self.conn,
            document_type="completion_acceptance_certificate",
            stage="completed_acceptance",
            schema_version="acceptance.v1",
            fields={
                **ACCEPTANCE_FIELDS,
                "project.name": "OCR误识别的其他项目",
            },
            project_id="project-confirmed-values",
        )
        project_name = next(
            field for field in review["fields"] if field["semanticKey"] == "project.name"
        )
        review = save_decisions(
            self.conn,
            review_id=review["id"],
            expected_review_version=review["reviewVersion"],
            decisions=[{
                "fieldId": project_name["id"],
                "decision": "modified",
                "confirmedValue": "项目-project-confirmed-values",
                "reason": "根据验收证明标题人工复核纠正",
            }],
            actor=ACTOR,
            now=NOW,
        )

        result = confirm_review(
            self.conn,
            review_id=review["id"],
            expected_review_version=review["reviewVersion"],
            idempotency_key="confirm:acceptance:confirmed-values",
            actor=ACTOR,
            allowed_project_ids=("project-confirmed-values",),
            form_template_version="acceptance-form.v1",
            now=NOW,
        )

        self.assertEqual(result["projectId"], "project-confirmed-values")
        project = self.conn.execute(
            "SELECT project_status FROM project_records WHERE id = ?",
            ("project-confirmed-values",),
        ).fetchone()
        self.assertEqual(project["project_status"], "completed_acceptance")

    def test_final_determination_keeps_amount_semantics_separate_and_rolls_back_on_event_failure(self):
        insert_project(self.conn, "project-final", "second_audit", 6)
        review = ready_review(
            self.conn,
            document_type="final_audit_determination",
            stage="conclusion",
            schema_version="final_determination.v1",
            fields=FINAL_FIELDS,
            project_id="project-final",
        )
        result = confirm_review(
            self.conn,
            review_id=review["id"],
            expected_review_version=review["reviewVersion"],
            idempotency_key="confirm:final:1",
            actor=ACTOR,
            allowed_project_ids=("project-final",),
            form_template_version="final-form.v1",
            now=NOW,
        )
        fact = self.conn.execute("SELECT * FROM project_audit_determinations").fetchone()
        self.assertEqual(fact["engineering_determined_amount_fen"], 90_000_000)
        self.assertEqual(fact["review_fee_deduction_fen"], 1_000_000)
        self.assertEqual(fact["final_settlement_amount_fen"], 89_000_000)
        events = self.conn.execute(
            "SELECT transition_type FROM project_lifecycle_events ORDER BY created_at, id"
        ).fetchall()
        self.assertEqual({row["transition_type"] for row in events}, {"forward", "settlement_base_updated"})
        self.assertEqual(result["projectId"], "project-final")

        insert_project(self.conn, "project-rollback", "second_audit", 6)
        rollback_review = ready_review(
            self.conn,
            document_type="final_audit_determination",
            stage="conclusion",
            schema_version="final_determination.v1",
            fields={**FINAL_FIELDS, "project.name": "项目-project-rollback"},
            project_id="project-rollback",
        )
        self.conn.execute(
            """
            CREATE TRIGGER fail_lifecycle_event
            BEFORE INSERT ON project_lifecycle_events
            WHEN NEW.project_id = 'project-rollback'
            BEGIN SELECT RAISE(ABORT, 'forced event failure'); END
            """
        )
        with self.assertRaises(sqlite3.IntegrityError):
            confirm_review(
                self.conn,
                review_id=rollback_review["id"],
                expected_review_version=rollback_review["reviewVersion"],
                idempotency_key="confirm:final:rollback",
                actor=ACTOR,
                allowed_project_ids=("project-rollback",),
                form_template_version="final-form.v1",
                now=NOW,
            )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM project_audit_determinations WHERE project_id = 'project-rollback'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM stage_form_snapshots WHERE project_id = 'project-rollback'"
            ).fetchone()[0],
            0,
        )
        project = self.conn.execute("SELECT * FROM project_records WHERE id = 'project-rollback'").fetchone()
        review_row = self.conn.execute("SELECT * FROM document_reviews WHERE id = ?", (rollback_review["id"],)).fetchone()
        self.assertEqual(project["project_status"], "second_audit")
        self.assertNotEqual(review_row["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
