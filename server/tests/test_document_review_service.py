import json
import sqlite3
import unittest
from pathlib import Path

import server.document_review_service as review_service
from server.document_repository import (
    add_document_pages,
    create_document_upload,
    create_recognition_job,
)
from server.document_review_service import (
    CriticalBulkAcceptError,
    ReviewDecisionValidationError,
    ReviewVersionConflictError,
    open_review,
    review_detail,
    save_decisions,
)


NOW = "2026-07-14T01:00:00Z"
ACTOR = {"id": "reviewer-1", "name": "复核员"}


def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).resolve().parents[1] / "schema.sql"
    conn.executescript(schema.read_text(encoding="utf-8"))
    return conn


def create_ready_document(conn, fields):
    upload = create_document_upload(
        conn,
        document_type="construction_contract",
        lifecycle_stage="contract_handoff",
        original_name="施工合同.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256="contract-hash",
        relative_path="documents/contract-hash.pdf",
        uploaded_by=ACTOR["id"],
        now=NOW,
    )
    page = add_document_pages(
        conn,
        document_version_id=upload["version"]["id"],
        pages=[{
            "id": "page-1",
            "page_number": 1,
            "relative_path": "documents/page-0001.png",
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
        schema_version="contract.v1",
        idempotency_key="recognize:contract",
        now=NOW,
    )
    conn.execute(
        "UPDATE recognition_jobs SET status = 'review_ready', finished_at = ? WHERE id = ?",
        (NOW, job["id"]),
    )
    conn.execute(
        "UPDATE documents SET status = 'review_ready' WHERE id = ?",
        (upload["document"]["id"],),
    )
    for index, (semantic_key, normalized_value) in enumerate(fields.items(), start=1):
        field_id = f"field-{index}"
        conn.execute(
            """
            INSERT INTO extracted_fields
            (id, recognition_job_id, semantic_key, raw_value, normalized_value_json,
             confidence, validation_status, source_kind, model_version, created_at)
            VALUES (?, ?, ?, ?, ?, 0.95, 'valid', 'ocr', 'test-v1', ?)
            """,
            (
                field_id,
                job["id"],
                semantic_key,
                str(normalized_value),
                json.dumps(normalized_value, ensure_ascii=False),
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO evidence_anchors
            (id, extracted_field_id, document_version_id, document_page_id,
             bbox_json, source_text, image_crop_relative_path, created_at)
            VALUES (?, ?, ?, ?, '[0.1,0.1,0.2,0.05]', ?, '', ?)
            """,
            (
                f"anchor-{index}",
                field_id,
                upload["version"]["id"],
                page["id"],
                str(normalized_value),
                NOW,
            ),
        )
    conn.commit()
    return upload, job


CONTRACT_FIELDS = {
    "project.name": "示范工程",
    "party.owner": "建设单位",
    "party.contractor": "江苏悦铂特建设工程有限公司",
    "contract.amount": 100_000_000,
    "contract.signed_date": "2026-07-01",
    "contract.payment_terms": ["竣工验收后支付60%"],
    "contract.number": "HT-001",
    "contract.type": "施工总承包合同",
}


class DocumentReviewServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_conn()
        self.upload, self.job = create_ready_document(self.conn, CONTRACT_FIELDS)
        self.review = open_review(
            self.conn,
            document_id=self.upload["document"]["id"],
            recognition_job_id=self.job["id"],
            actor=ACTOR,
            allowed_project_ids=(),
            now=NOW,
        )

    def tearDown(self):
        self.conn.close()

    def test_decision_types_preserve_ai_values_and_recalculate_blockers(self):
        fields = {item["semanticKey"]: item for item in self.review["fields"]}
        amount = fields["contract.amount"]
        decisions = []
        for semantic_key in (
            "project.name",
            "party.owner",
            "party.contractor",
            "contract.signed_date",
            "contract.payment_terms",
        ):
            item = fields[semantic_key]
            decisions.append({
                "fieldId": item["id"],
                "decision": "accepted",
                "confirmedValue": item["aiValue"],
            })
        decisions.extend([
            {
                "fieldId": amount["id"],
                "decision": "modified",
                "confirmedValue": 99_000_000,
                "reason": "与合同盖章页大写金额复核一致",
            },
            {
                "fieldId": fields["contract.number"]["id"],
                "decision": "rejected",
                "reason": "扫描件未显示完整编号",
            },
            {
                "fieldId": fields["contract.type"]["id"],
                "decision": "unrecognized",
                "reason": "原件该区域模糊",
            },
        ])

        detail = self.review
        for decision in decisions:
            detail = save_decisions(
                self.conn,
                review_id=self.review["id"],
                expected_review_version=detail["reviewVersion"],
                decisions=[decision],
                actor=ACTOR,
                now=NOW,
            )

        self.assertEqual(detail["reviewVersion"], len(decisions))
        self.assertEqual(detail["blockers"], [])
        stored = self.conn.execute(
            """
            SELECT ai_value_json, confirmed_value_json, reviewer_id, reviewer_name
            FROM review_decisions WHERE extracted_field_id = ?
            """,
            (amount["id"],),
        ).fetchone()
        self.assertEqual(json.loads(stored["ai_value_json"]), 100_000_000)
        self.assertEqual(json.loads(stored["confirmed_value_json"]), 99_000_000)
        self.assertEqual((stored["reviewer_id"], stored["reviewer_name"]), ("reviewer-1", "复核员"))

    def test_modified_decision_requires_reason_and_critical_bulk_accept_is_denied(self):
        fields = {item["semanticKey"]: item for item in self.review["fields"]}
        with self.assertRaises(ReviewDecisionValidationError):
            save_decisions(
                self.conn,
                review_id=self.review["id"],
                expected_review_version=0,
                decisions=[{
                    "fieldId": fields["contract.amount"]["id"],
                    "decision": "modified",
                    "confirmedValue": 99_000_000,
                }],
                actor=ACTOR,
                now=NOW,
            )
        with self.assertRaises(CriticalBulkAcceptError):
            save_decisions(
                self.conn,
                review_id=self.review["id"],
                expected_review_version=0,
                decisions=[
                    {
                        "fieldId": fields["project.name"]["id"],
                        "decision": "accepted",
                        "confirmedValue": "示范工程",
                    },
                    {
                        "fieldId": fields["party.owner"]["id"],
                        "decision": "accepted",
                        "confirmedValue": "建设单位",
                    },
                ],
                actor=ACTOR,
                bulk=True,
                now=NOW,
            )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0],
            0,
        )

    def test_critical_fields_cannot_be_bulk_accepted_by_omitting_the_bulk_flag(self):
        fields = {item["semanticKey"]: item for item in self.review["fields"]}

        with self.assertRaises(CriticalBulkAcceptError):
            save_decisions(
                self.conn,
                review_id=self.review["id"],
                expected_review_version=0,
                decisions=[
                    {
                        "fieldId": fields["project.name"]["id"],
                        "decision": "accepted",
                        "confirmedValue": fields["project.name"]["aiValue"],
                    },
                    {
                        "fieldId": fields["party.owner"]["id"],
                        "decision": "accepted",
                        "confirmedValue": fields["party.owner"]["aiValue"],
                    },
                ],
                actor=ACTOR,
                now=NOW,
            )

    def test_modified_values_replace_failed_ocr_values_and_are_revalidated(self):
        self.conn.close()
        self.conn = memory_conn()
        fields = {**CONTRACT_FIELDS, "contract.amount": None}
        upload, job = create_ready_document(self.conn, fields)
        review = open_review(
            self.conn,
            document_id=upload["document"]["id"],
            recognition_job_id=job["id"],
            actor=ACTOR,
            allowed_project_ids=(),
            now=NOW,
        )
        by_key = {item["semanticKey"]: item for item in review["fields"]}

        detail = save_decisions(
            self.conn,
            review_id=review["id"],
            expected_review_version=0,
            decisions=[{
                "fieldId": by_key["contract.amount"]["id"],
                "decision": "modified",
                "confirmedValue": "not-an-integer-fen-value",
                "reason": "人工录入待复核",
            }],
            actor=ACTOR,
            now=NOW,
        )
        codes = {item["code"] for item in detail["blockers"]}
        self.assertIn("field_normalization_failed", codes)

        detail = save_decisions(
            self.conn,
            review_id=review["id"],
            expected_review_version=detail["reviewVersion"],
            decisions=[{
                "fieldId": by_key["contract.amount"]["id"],
                "decision": "modified",
                "confirmedValue": 99_000_000,
                "reason": "根据合同盖章页人工核对",
            }],
            actor=ACTOR,
            now=NOW,
        )
        codes = {
            item["code"]
            for item in detail["blockers"]
            if item["field"] == "contract.amount"
        }
        self.assertNotIn("critical_field_missing", codes)
        self.assertNotIn("field_normalization_failed", codes)

    def test_stale_review_version_conflicts_without_partial_writes(self):
        fields = {item["semanticKey"]: item for item in self.review["fields"]}
        first = fields["project.name"]
        save_decisions(
            self.conn,
            review_id=self.review["id"],
            expected_review_version=0,
            decisions=[{
                "fieldId": first["id"],
                "decision": "accepted",
                "confirmedValue": first["aiValue"],
            }],
            actor=ACTOR,
            now=NOW,
        )

        with self.assertRaises(ReviewVersionConflictError) as raised:
            save_decisions(
                self.conn,
                review_id=self.review["id"],
                expected_review_version=0,
                decisions=[{
                    "fieldId": fields["party.owner"]["id"],
                    "decision": "accepted",
                    "confirmedValue": "建设单位",
                }],
                actor=ACTOR,
                now=NOW,
            )
        self.assertEqual(raised.exception.current_version, 1)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0],
            1,
        )

    def test_review_detail_exposes_evidence_without_storage_paths(self):
        detail = review_detail(self.conn, self.review["id"])

        self.assertEqual(detail["document"]["name"], "施工合同.pdf")
        self.assertEqual(detail["allowedCommands"], ["save_decisions"])
        self.assertTrue(detail["fields"][0]["anchors"])
        rendered = json.dumps(detail, ensure_ascii=False)
        self.assertNotIn("relative_path", rendered)
        self.assertNotIn("documents/page-0001.png", rendered)

    def test_transaction_neutral_save_leaves_commit_and_rollback_to_caller(self):
        operation = getattr(review_service, "save_decisions_in_transaction", None)
        self.assertIsNotNone(operation)
        field = next(
            item for item in self.review["fields"]
            if item["semanticKey"] == "project.name"
        )

        self.conn.execute("BEGIN IMMEDIATE")
        detail = operation(
            self.conn,
            review_id=self.review["id"],
            expected_review_version=0,
            decisions=[{
                "fieldId": field["id"],
                "decision": "accepted",
                "confirmedValue": field["aiValue"],
            }],
            actor=ACTOR,
            now=NOW,
        )

        self.assertEqual(detail["reviewVersion"], 1)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0],
            1,
        )
        self.conn.rollback()
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM review_decisions").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT review_version FROM document_reviews WHERE id = ?",
                (self.review["id"],),
            ).fetchone()[0],
            0,
        )

    def test_transaction_neutral_confirmation_leaves_rollback_to_caller(self):
        operation = getattr(review_service, "confirm_review_in_transaction", None)
        self.assertIsNotNone(operation)
        detail = self.review
        for field in self.review["fields"]:
            detail = save_decisions(
                self.conn,
                review_id=self.review["id"],
                expected_review_version=detail["reviewVersion"],
                decisions=[{
                    "fieldId": field["id"],
                    "decision": "accepted",
                    "confirmedValue": field["aiValue"],
                }],
                actor=ACTOR,
                now=NOW,
            )

        self.conn.execute("BEGIN IMMEDIATE")
        result = operation(
            self.conn,
            review_id=self.review["id"],
            expected_review_version=detail["reviewVersion"],
            idempotency_key="confirm:contract:transaction-owner",
            actor=ACTOR,
            allowed_project_ids=(),
            form_template_version="contract-form.v1",
            project_code_generator=lambda *_args: "20260701-YBT-001",
            now=NOW,
        )

        self.assertEqual(result["status"], "created")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0],
            1,
        )
        self.conn.rollback()
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT status FROM document_reviews WHERE id = ?",
                (self.review["id"],),
            ).fetchone()[0],
            "in_review",
        )

    def test_accepted_manual_field_without_anchor_has_no_evidence_blocker(self):
        field = next(
            item for item in self.review["fields"]
            if item["semanticKey"] == "project.name"
        )
        self.conn.execute(
            "UPDATE extracted_fields SET source_kind = 'manual' WHERE id = ?",
            (field["id"],),
        )
        self.conn.execute(
            "DELETE FROM evidence_anchors WHERE extracted_field_id = ?",
            (field["id"],),
        )
        self.conn.commit()

        detail = save_decisions(
            self.conn,
            review_id=self.review["id"],
            expected_review_version=0,
            decisions=[{
                "fieldId": field["id"],
                "decision": "accepted",
                "confirmedValue": field["aiValue"],
            }],
            actor=ACTOR,
            now=NOW,
        )

        blockers = {
            (item["code"], item["field"])
            for item in detail["blockers"]
        }
        self.assertNotIn(("evidence_anchor_missing", "project.name"), blockers)


if __name__ == "__main__":
    unittest.main()
