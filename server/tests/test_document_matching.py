import sqlite3
import unittest

from server.document_matching import (
    match_document_to_projects,
    validate_document_project_link,
)
from server.document_repository import create_document_upload
from server.document_repository import (
    claim_next_recognition_job,
    create_recognition_job,
    save_recognition_result,
)
from server.migrations import apply_pending_migrations


NOW = "2026-07-13T01:00:00Z"


def _field(key, value):
    return {
        "semantic_key": key,
        "raw_value": str(value),
        "normalized_value": value,
    }


class DocumentMatchingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute(
            """
            CREATE TABLE project_records (
              id TEXT PRIMARY KEY,
              project_code TEXT UNIQUE NOT NULL,
              project_name TEXT NOT NULL,
              owner_unit TEXT DEFAULT '',
              construction_unit TEXT DEFAULT '',
              project_status TEXT DEFAULT 'under_construction',
              lifecycle_version INTEGER NOT NULL DEFAULT 0,
              contract_amount REAL DEFAULT 0,
              is_deleted INTEGER DEFAULT 0
            )
            """
        )
        self._project(
            "project-1",
            "20240618-GL-001",
            "区直学校校舍维修工程",
            "盐南教育发展中心",
            "江苏广良建设工程有限公司",
            2616381.74,
            "second_audit",
        )
        self._project(
            "project-2",
            "20250001-TX-001",
            "产业园改造工程",
            "产业园建设单位",
            "盐城市腾兴市政绿化工程有限公司",
            5000000,
            "under_construction",
        )
        self.conn.commit()
        apply_pending_migrations(self.conn)
        self.project_scope = {"project-1", "project-2"}

    def tearDown(self):
        self.conn.close()

    def _project(self, project_id, code, name, owner, contractor, amount, status):
        self.conn.execute(
            """
            INSERT INTO project_records
            (id, project_code, project_name, owner_unit, construction_unit,
             contract_amount, project_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, code, name, owner, contractor, amount, status),
        )

    def _document(self, project_id, sha256, *, document_type="final_audit_determination"):
        created = create_document_upload(
            self.conn,
            document_type=document_type,
            lifecycle_stage="conclusion",
            project_id=project_id,
            original_name="审定单.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256=sha256,
            relative_path=f"documents/{project_id}/{sha256}.pdf",
            uploaded_by="user-1",
            now=NOW,
        )
        return created

    def _recognized_document(self, fields):
        created = self._document(None, "unbound-recognized-document")
        job = create_recognition_job(
            self.conn,
            document_version_id=created["version"]["id"],
            adapter_key="test",
            schema_version="final_determination.v1",
            idempotency_key="recognize-unbound-document",
            now=NOW,
        )
        self.conn.commit()
        claimed = claim_next_recognition_job(
            self.conn, worker_id="worker-1", now=NOW
        )
        self.assertEqual(claimed["id"], job["id"])
        save_recognition_result(
            self.conn,
            job_id=job["id"],
            worker_id="worker-1",
            model_version="test-model",
            provider_request_id="test-request",
            blocks=[],
            fields=fields,
            now=NOW,
        )
        self.conn.commit()
        return created

    def test_matching_queries_only_the_explicit_project_scope(self):
        result = match_document_to_projects(
            self.conn,
            [_field("project.name", "产业园改造工程")],
            allowed_project_ids={"project-1"},
        )

        self.assertEqual([item.project_id for item in result.candidates], ["project-1"])
        self.assertIsNone(result.recommendation)

    def test_exact_project_code_match_is_explainable_but_not_auto_confirmed(self):
        result = match_document_to_projects(
            self.conn,
            [
                _field("project.code", "20240618-GL-001"),
                _field("project.name", "完全不同的OCR名称"),
            ],
            allowed_project_ids=self.project_scope,
        )

        self.assertEqual(result.recommendation.project_id, "project-1")
        self.assertIn("project_code_exact", result.recommendation.contributions)
        self.assertFalse(result.auto_confirmed)

    def test_normalized_project_name_can_recommend_a_unique_project(self):
        result = match_document_to_projects(
            self.conn,
            [_field("project.name", " 区直学校 校舍维修项目 ")],
            allowed_project_ids=self.project_scope,
        )

        self.assertEqual(result.recommendation.project_id, "project-1")
        self.assertIn("project_name_normalized", result.recommendation.contributions)

    def test_both_party_mismatches_override_a_high_name_score(self):
        result = match_document_to_projects(
            self.conn,
            [
                _field("project.name", "区直学校校舍维修工程"),
                _field("party.owner", "另一家建设单位"),
                _field("party.contractor", "另一家施工单位"),
            ],
            allowed_project_ids=self.project_scope,
        )

        candidate = next(item for item in result.candidates if item.project_id == "project-1")
        self.assertIn("both_parties_mismatch", candidate.conflicts)
        self.assertIsNone(result.recommendation)

    def test_amount_order_of_magnitude_conflict_is_a_hard_blocker(self):
        result = match_document_to_projects(
            self.conn,
            [
                _field("project.code", "20240618-GL-001"),
                _field("contract.amount_reference", 26163817400),
            ],
            allowed_project_ids=self.project_scope,
        )

        self.assertIn(
            "amount_magnitude_conflict", {item["code"] for item in result.blockers}
        )
        self.assertIsNone(result.recommendation)

    def test_same_name_projects_are_reported_as_ambiguous(self):
        self._project(
            "project-3",
            "20260001-GL-002",
            "区直学校校舍维修项目",
            "盐南教育发展中心",
            "江苏广良建设工程有限公司",
            2616381.74,
            "second_audit",
        )
        self.conn.commit()

        result = match_document_to_projects(
            self.conn,
            [_field("project.name", "区直学校校舍维修工程")],
            allowed_project_ids={*self.project_scope, "project-3"},
        )

        self.assertIn("ambiguous_project_match", {item["code"] for item in result.blockers})
        self.assertIsNone(result.recommendation)

    def test_duplicate_confirmed_hash_on_another_project_blocks_link(self):
        confirmed = self._document("project-1", "same-confirmed-hash")
        self.conn.execute(
            "UPDATE documents SET status = 'confirmed' WHERE id = ?",
            (confirmed["document"]["id"],),
        )
        incoming = self._document("project-2", "same-confirmed-hash")
        self.conn.commit()

        blockers = validate_document_project_link(
            self.conn,
            incoming["document"]["id"],
            "project-2",
            allowed_project_ids=self.project_scope,
        )

        self.assertIn("duplicate_confirmed_hash", {item["code"] for item in blockers})

    def test_final_determination_bound_to_another_project_is_blocked(self):
        document = self._document("project-1", "final-project-1")
        self.conn.commit()

        blockers = validate_document_project_link(
            self.conn,
            document["document"]["id"],
            "project-2",
            allowed_project_ids=self.project_scope,
        )

        self.assertIn("document_project_conflict", {item["code"] for item in blockers})

    def test_unbound_document_cannot_link_to_a_nonrecommended_project(self):
        document = self._recognized_document(
            [
                {
                    **_field("project.name", "区直学校校舍维修工程"),
                    "anchors": [],
                }
            ]
        )

        blockers = validate_document_project_link(
            self.conn,
            document["document"]["id"],
            "project-2",
            allowed_project_ids={"project-1", "project-2"},
        )

        self.assertIn(
            "target_project_not_recommended", {item["code"] for item in blockers}
        )


if __name__ == "__main__":
    unittest.main()
