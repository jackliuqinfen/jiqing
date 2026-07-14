import sqlite3
import unittest

from server.document_repository import (
    EvidenceGraphMismatchError,
    RecognitionIdempotencyConflictError,
    RecognitionLeaseError,
    ReviewImmutableError,
    add_document_pages,
    claim_next_recognition_job,
    create_document_upload,
    create_recognition_job,
    create_review,
    mark_recognition_failed,
    mark_review_confirmed,
    review_snapshot,
    save_recognition_result,
    upsert_review_decision,
)
from server.migrations import apply_pending_migrations


NOW = "2026-07-13T01:00:00Z"


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
    conn.executemany(
        "INSERT INTO project_records (id) VALUES (?)",
        (("project-1",), ("project-2",)),
    )
    conn.commit()
    apply_pending_migrations(conn)
    return conn


def upload(
    conn,
    *,
    project_id="project-1",
    sha256="hash-1",
    document_id=None,
    uploaded_by="user-1",
):
    return create_document_upload(
        conn,
        document_type="construction_contract",
        lifecycle_stage="contract_handoff",
        project_id=project_id,
        original_name="合同.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256=sha256,
        relative_path=f"documents/{project_id}/{sha256}.pdf",
        uploaded_by=uploaded_by,
        document_id=document_id,
        now=NOW,
    )


class DocumentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_conn()

    def tearDown(self):
        self.conn.close()

    def test_same_hash_in_same_scope_replays_but_cross_project_is_reported(self):
        first = upload(self.conn)
        replay = upload(self.conn)
        cross_project = upload(self.conn, project_id="project-2")

        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["version"]["id"], first["version"]["id"])
        self.assertFalse(cross_project["replayed"])
        self.assertEqual(cross_project["cross_project_duplicate_count"], 1)
        self.assertNotIn("duplicate_versions", cross_project)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0],
            2,
        )

    def test_unbound_same_hash_is_scoped_to_the_uploading_user(self):
        first = upload(self.conn, project_id=None, uploaded_by="user-1")
        second = upload(self.conn, project_id=None, uploaded_by="user-2")

        self.assertFalse(second["replayed"])
        self.assertNotEqual(second["document"]["id"], first["document"]["id"])

    def test_new_version_is_monotonic_and_original_version_is_not_overwritten(self):
        first = upload(self.conn)
        second = upload(
            self.conn,
            sha256="hash-2",
            document_id=first["document"]["id"],
        )

        versions = self.conn.execute(
            "SELECT version_no, sha256 FROM document_versions WHERE document_id = ? ORDER BY version_no",
            (first["document"]["id"],),
        ).fetchall()
        current = self.conn.execute(
            "SELECT current_version_id FROM documents WHERE id = ?",
            (first["document"]["id"],),
        ).fetchone()[0]
        self.assertEqual([(row[0], row[1]) for row in versions], [(1, "hash-1"), (2, "hash-2")])
        self.assertEqual(current, second["version"]["id"])

    def test_job_claim_is_exclusive_and_failed_jobs_obey_retry_limit(self):
        created = upload(self.conn)
        job = create_recognition_job(
            self.conn,
            document_version_id=created["version"]["id"],
            adapter_key="manual-v1",
            schema_version="contract.v1",
            idempotency_key="recognize:1",
            max_attempts=2,
            now=NOW,
        )
        self.conn.commit()

        first_claim = claim_next_recognition_job(
            self.conn, worker_id="worker-1", now=NOW
        )
        second_claim = claim_next_recognition_job(
            self.conn, worker_id="worker-2", now=NOW
        )
        self.assertEqual(first_claim["id"], job["id"])
        self.assertEqual(first_claim["attempts"], 1)
        self.assertIsNone(second_claim)

        mark_recognition_failed(
            self.conn,
            job_id=job["id"],
            worker_id="worker-1",
            error_code="provider_timeout",
            error_message="timeout",
            now=NOW,
        )
        self.conn.commit()
        retry = claim_next_recognition_job(
            self.conn, worker_id="worker-2", now=NOW
        )
        self.assertEqual(retry["attempts"], 2)
        mark_recognition_failed(
            self.conn,
            job_id=job["id"],
            worker_id="worker-2",
            error_code="provider_timeout",
            error_message="timeout",
            now=NOW,
        )
        self.conn.commit()
        self.assertIsNone(
            claim_next_recognition_job(self.conn, worker_id="worker-3", now=NOW)
        )

    def test_recognition_result_persists_normalized_evidence_anchors(self):
        created, page, job = self._document_page_job()
        save_recognition_result(
            self.conn,
            job_id=job["id"],
            worker_id="worker-1",
            model_version="manual-1",
            provider_request_id="request-1",
            blocks=[{
                "id": "block-1",
                "page_id": page["id"],
                "block_type": "text",
                "raw_text": "合同金额100万元",
                "confidence": 0.98,
                "bbox": [0.1, 0.2, 0.3, 0.04],
            }],
            fields=[{
                "id": "field-1",
                "semantic_key": "contract_amount",
                "raw_value": "100万元",
                "normalized_value": {"fen": 100000000},
                "confidence": 0.96,
                "anchors": [{
                    "id": "anchor-1",
                    "page_id": page["id"],
                    "bbox": [0.1, 0.2, 0.3, 0.04],
                    "source_text": "100万元",
                }],
            }],
            now=NOW,
        )

        field = self.conn.execute(
            "SELECT semantic_key, normalized_value_json FROM extracted_fields WHERE id = 'field-1'"
        ).fetchone()
        anchor = self.conn.execute(
            "SELECT bbox_json, source_text FROM evidence_anchors WHERE id = 'anchor-1'"
        ).fetchone()
        self.assertEqual(field["semantic_key"], "contract_amount")
        self.assertEqual(field["normalized_value_json"], '{"fen":100000000}')
        self.assertEqual(anchor["bbox_json"], "[0.1,0.2,0.3,0.04]")
        self.assertEqual(anchor["source_text"], "100万元")

    def test_decision_overwrite_preserves_history_and_confirmation_is_immutable(self):
        created, _page, job = self._document_page_job()
        save_recognition_result(
            self.conn,
            job_id=job["id"],
            worker_id="worker-1",
            model_version="manual-1",
            provider_request_id="request-1",
            blocks=[],
            fields=[{
                "id": "field-1",
                "semantic_key": "contract_number",
                "raw_value": "HT-01",
                "normalized_value": "HT-01",
                "confidence": 0.9,
                "anchors": [],
            }],
            now=NOW,
        )
        review = create_review(
            self.conn,
            document_id=created["document"]["id"],
            document_version_id=created["version"]["id"],
            recognition_job_id=job["id"],
            project_id="project-1",
            now=NOW,
        )
        first = upsert_review_decision(
            self.conn,
            review_id=review["id"],
            extracted_field_id="field-1",
            decision="accepted",
            ai_value="HT-01",
            confirmed_value="HT-01",
            reviewer_id="reviewer-1",
            reviewer_name="复核员",
            now=NOW,
        )
        upsert_review_decision(
            self.conn,
            review_id=review["id"],
            extracted_field_id="field-1",
            decision="modified",
            ai_value="HT-01",
            confirmed_value="HT-001",
            reviewer_id="reviewer-1",
            reviewer_name="复核员",
            now=NOW,
        )
        history = self.conn.execute(
            "SELECT decision, confirmed_value_json FROM review_decision_history WHERE review_decision_id = ?",
            (first["id"],),
        ).fetchall()
        self.assertEqual(
            [(row["decision"], row["confirmed_value_json"]) for row in history],
            [("accepted", '"HT-01"')],
        )

        snapshot = mark_review_confirmed(
            self.conn,
            review_id=review["id"],
            idempotency_key="confirm:review-1",
            project_id="project-1",
            stage_key="contract_handoff",
            form_template_version="contract-form.v1",
            extraction_schema_version="contract.v1",
            values={"contract_number": "HT-001"},
            evidence_manifest={},
            reviewer_id="reviewer-1",
            reviewer_name="复核员",
            now=NOW,
        )
        replay = mark_review_confirmed(
            self.conn,
            review_id=review["id"],
            idempotency_key="confirm:review-1",
            project_id="project-1",
            stage_key="contract_handoff",
            form_template_version="contract-form.v1",
            extraction_schema_version="contract.v1",
            values={"contract_number": "tampered"},
            evidence_manifest={},
            reviewer_id="reviewer-1",
            reviewer_name="复核员",
            now=NOW,
        )
        self.assertEqual(replay["id"], snapshot["id"])
        self.assertEqual(replay["values_json"], '{"contract_number":"HT-001"}')
        with self.assertRaises(ReviewImmutableError):
            mark_review_confirmed(
                self.conn,
                review_id=review["id"],
                idempotency_key="confirm:different",
                project_id="project-1",
                stage_key="contract_handoff",
                form_template_version="contract-form.v1",
                extraction_schema_version="contract.v1",
                values={},
                evidence_manifest={},
                reviewer_id="reviewer-1",
                reviewer_name="复核员",
                now=NOW,
            )
        self.assertEqual(review_snapshot(self.conn, review["id"])["status"], "confirmed")

    def test_idempotency_key_cannot_replay_a_job_for_another_version(self):
        first = upload(self.conn, sha256="hash-first")
        second = upload(self.conn, project_id="project-2", sha256="hash-second")
        create_recognition_job(
            self.conn,
            document_version_id=first["version"]["id"],
            adapter_key="manual-v1",
            schema_version="contract.v1",
            idempotency_key="shared-key",
            now=NOW,
        )

        with self.assertRaises(RecognitionIdempotencyConflictError):
            create_recognition_job(
                self.conn,
                document_version_id=second["version"]["id"],
                adapter_key="manual-v1",
                schema_version="contract.v1",
                idempotency_key="shared-key",
                now=NOW,
            )

    def test_cross_version_page_and_wrong_worker_are_rejected_before_writes(self):
        first, _first_page, job = self._document_page_job()
        second = upload(self.conn, project_id="project-2", sha256="hash-second")
        second_page = add_document_pages(
            self.conn,
            document_version_id=second["version"]["id"],
            pages=[{
                "id": "page-second",
                "page_number": 1,
                "relative_path": "documents/second/page-0001.png",
                "width_px": 2480,
                "height_px": 3508,
                "dpi": 300,
                "preprocessing_version": "render-v1",
            }],
            now=NOW,
        )[0]

        with self.assertRaises(RecognitionLeaseError):
            save_recognition_result(
                self.conn,
                job_id=job["id"],
                worker_id="worker-2",
                model_version="manual-1",
                provider_request_id="request-wrong-worker",
                blocks=[],
                fields=[],
                now=NOW,
            )
        with self.assertRaises(EvidenceGraphMismatchError):
            save_recognition_result(
                self.conn,
                job_id=job["id"],
                worker_id="worker-1",
                model_version="manual-1",
                provider_request_id="request-cross-page",
                blocks=[],
                fields=[{
                    "id": "cross-field",
                    "semantic_key": "contract_number",
                    "raw_value": "HT-01",
                    "normalized_value": "HT-01",
                    "anchors": [{
                        "id": "cross-anchor",
                        "page_id": second_page["id"],
                        "bbox": [0.1, 0.1, 0.2, 0.1],
                    }],
                }],
                now=NOW,
            )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM extracted_fields WHERE recognition_job_id = ?",
                (job["id"],),
            ).fetchone()[0],
            0,
        )

        with self.assertRaises(EvidenceGraphMismatchError):
            create_review(
                self.conn,
                document_id=second["document"]["id"],
                document_version_id=first["version"]["id"],
                recognition_job_id=job["id"],
                project_id="project-1",
                now=NOW,
            )

    def test_old_version_job_does_not_change_current_document_status(self):
        first = upload(self.conn, sha256="hash-v1")
        upload(
            self.conn,
            sha256="hash-v2",
            document_id=first["document"]["id"],
        )

        create_recognition_job(
            self.conn,
            document_version_id=first["version"]["id"],
            adapter_key="manual-v1",
            schema_version="contract.v1",
            idempotency_key="old-version-job",
            now=NOW,
        )

        status = self.conn.execute(
            "SELECT status FROM documents WHERE id = ?",
            (first["document"]["id"],),
        ).fetchone()[0]
        self.assertEqual(status, "uploaded")

    def test_confirmation_rejects_unknown_or_cross_job_evidence(self):
        created, _page, job = self._document_page_job()
        save_recognition_result(
            self.conn,
            job_id=job["id"],
            worker_id="worker-1",
            model_version="manual-1",
            provider_request_id="request-1",
            blocks=[],
            fields=[{
                "id": "field-1",
                "semantic_key": "contract_number",
                "raw_value": "HT-01",
                "normalized_value": "HT-01",
                "anchors": [],
            }],
            now=NOW,
        )
        review = create_review(
            self.conn,
            document_id=created["document"]["id"],
            document_version_id=created["version"]["id"],
            recognition_job_id=job["id"],
            project_id="project-1",
            now=NOW,
        )

        with self.assertRaises(EvidenceGraphMismatchError):
            mark_review_confirmed(
                self.conn,
                review_id=review["id"],
                idempotency_key="confirm:invalid-anchor",
                project_id="project-1",
                stage_key="contract_handoff",
                form_template_version="contract-form.v1",
                extraction_schema_version="contract.v1",
                values={"contract_number": "HT-01"},
                evidence_manifest={"contract_number": ["missing-anchor"]},
                reviewer_id="reviewer-1",
                reviewer_name="复核员",
                now=NOW,
            )

    def test_review_requires_review_ready_job_for_the_current_version(self):
        created = upload(self.conn)
        queued_job = create_recognition_job(
            self.conn,
            document_version_id=created["version"]["id"],
            adapter_key="manual-v1",
            schema_version="contract.v1",
            idempotency_key="queued-job",
            now=NOW,
        )

        with self.assertRaises(EvidenceGraphMismatchError):
            create_review(
                self.conn,
                document_id=created["document"]["id"],
                document_version_id=created["version"]["id"],
                recognition_job_id=queued_job["id"],
                project_id="project-1",
                now=NOW,
            )

    def test_review_confirmation_rejects_a_version_superseded_after_review_opened(self):
        created, _page, job = self._document_page_job()
        save_recognition_result(
            self.conn,
            job_id=job["id"],
            worker_id="worker-1",
            model_version="manual-1",
            provider_request_id="request-1",
            blocks=[],
            fields=[],
            now=NOW,
        )
        review = create_review(
            self.conn,
            document_id=created["document"]["id"],
            document_version_id=created["version"]["id"],
            recognition_job_id=job["id"],
            project_id="project-1",
            now=NOW,
        )
        upload(
            self.conn,
            sha256="hash-new-version",
            document_id=created["document"]["id"],
        )

        with self.assertRaises(EvidenceGraphMismatchError):
            mark_review_confirmed(
                self.conn,
                review_id=review["id"],
                idempotency_key="confirm:stale-review",
                project_id="project-1",
                stage_key="contract_handoff",
                form_template_version="contract-form.v1",
                extraction_schema_version="contract.v1",
                values={},
                evidence_manifest={},
                reviewer_id="reviewer-1",
                reviewer_name="复核员",
                now=NOW,
            )

    def _document_page_job(self):
        created = upload(self.conn)
        pages = add_document_pages(
            self.conn,
            document_version_id=created["version"]["id"],
            pages=[{
                "id": "page-1",
                "page_number": 1,
                "relative_path": "documents/page-0001.png",
                "width_px": 2480,
                "height_px": 3508,
                "dpi": 300,
                "rotation_degrees": 0,
                "quality_score": 0.9,
                "preprocessing_version": "render-v1",
            }],
            now=NOW,
        )
        job = create_recognition_job(
            self.conn,
            document_version_id=created["version"]["id"],
            adapter_key="manual-v1",
            schema_version="contract.v1",
            idempotency_key="recognize:1",
            now=NOW,
        )
        self.conn.commit()
        claimed = claim_next_recognition_job(
            self.conn,
            worker_id="worker-1",
            now=NOW,
        )
        return created, pages[0], claimed


if __name__ == "__main__":
    unittest.main()
