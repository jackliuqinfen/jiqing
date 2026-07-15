import json
import sqlite3
import unittest

from server.contract_fallback_service import (
    ContractFallbackError,
    create_direct_fallback_review,
    create_fallback_review,
    manual_contract_fields,
    parse_external_contract_markdown,
)
from server.document_repository import create_document_upload, create_recognition_job
from server.migrations import apply_pending_migrations


NOW = "2026-07-15T02:00:00Z"


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


class ContractFallbackParserTests(unittest.TestCase):
    def test_valid_markdown_returns_whitelisted_source_preserving_fields(self):
        payload = {
            "schemaVersion": "contract.v1",
            "fields": {
                "project.name": {
                    "value": "悦铂特项目",
                    "evidence": "工程名称：悦铂特项目",
                    "page": 1,
                },
                "contract.amount": {
                    "value": "100.00万元",
                    "evidence": "合同价为100.00万元",
                    "page": 8,
                },
            },
        }

        fields = parse_external_contract_markdown(
            "# 合同识别结果\n```json\n"
            + json.dumps(payload, ensure_ascii=False)
            + "\n```"
        )

        self.assertEqual([field["semantic_key"] for field in fields], [
            "project.name",
            "contract.amount",
        ])
        self.assertEqual(fields[0]["raw_value"], "悦铂特项目")
        self.assertEqual(fields[0]["external_evidence"], "工程名称：悦铂特项目")
        self.assertEqual(fields[0]["external_page"], 1)
        self.assertEqual(fields[0]["source_kind"], "external_ai")
        self.assertEqual(fields[0]["anchors"], ())
        self.assertIsNone(fields[0]["confidence"])

    def test_parser_rejects_unknown_schema_keys_and_multiple_json_blocks(self):
        unknown = """```json
{"schemaVersion":"contract.v1","fields":{"project.fake":{"value":"x"}}}
```"""
        with self.assertRaisesRegex(ContractFallbackError, "不支持的合同字段"):
            parse_external_contract_markdown(unknown)

        duplicated = """```json
{"schemaVersion":"contract.v1","fields":{}}
```
```json
{"schemaVersion":"contract.v1","fields":{}}
```"""
        with self.assertRaisesRegex(ContractFallbackError, "只能包含一个"):
            parse_external_contract_markdown(duplicated)

    def test_parser_rejects_malformed_wrong_version_and_oversized_markdown(self):
        with self.assertRaisesRegex(ContractFallbackError, "JSON"):
            parse_external_contract_markdown("```json\n{broken}\n```")
        with self.assertRaisesRegex(ContractFallbackError, "版本"):
            parse_external_contract_markdown(
                "```json\n{\"schemaVersion\":\"acceptance.v1\",\"fields\":{}}\n```"
            )
        with self.assertRaisesRegex(ContractFallbackError, "过长"):
            parse_external_contract_markdown("x" * 131073)

    def test_parser_rejects_duplicate_keys_and_non_finite_numbers(self):
        duplicated_key = """```json
{"schemaVersion":"contract.v1","fields":{"project.name":{"value":"A"},"project.name":{"value":"B"}}}
```"""
        with self.assertRaisesRegex(ContractFallbackError, "重复"):
            parse_external_contract_markdown(duplicated_key)

        non_finite = """```json
{"schemaVersion":"contract.v1","fields":{"contract.amount":{"value":NaN}}}
```"""
        with self.assertRaisesRegex(ContractFallbackError, "非法数字"):
            parse_external_contract_markdown(non_finite)


class ContractFallbackReviewTests(unittest.TestCase):
    def setUp(self):
        self.conn = memory_conn()
        upload = create_document_upload(
            self.conn,
            document_type="construction_contract",
            lifecycle_stage="contract_handoff",
            project_id=None,
            original_name="悦铂特合同.pdf",
            mime_type="application/pdf",
            file_size=1024,
            sha256="fallback-contract-hash",
            relative_path="documents/fallback/contract.pdf",
            uploaded_by="editor-1",
            now=NOW,
        )
        self.source_job = create_recognition_job(
            self.conn,
            document_version_id=upload["version"]["id"],
            adapter_key="volcengine",
            schema_version="contract.v1",
            idempotency_key="source-recognition",
            now=NOW,
        )
        self.conn.execute(
            "UPDATE recognition_jobs SET status = 'manual_required' WHERE id = ?",
            (self.source_job["id"],),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_manual_review_materializes_blank_schema_without_fake_evidence(self):
        result = create_fallback_review(
            self.conn,
            source_job_id=self.source_job["id"],
            adapter_key="manual-entry",
            idempotency_key="manual-fallback-1",
            fields=[],
            actor={"id": "editor-1", "name": "刘建祥"},
            fallback_reason="ocr_failed",
            now=NOW,
        )
        self.conn.commit()

        self.assertEqual(result["status"], "review_ready")
        self.assertTrue(result["review_id"])
        self.assertEqual(result["source_recognition_job_id"], self.source_job["id"])
        rows = self.conn.execute(
            "SELECT source_kind, confidence FROM extracted_fields WHERE recognition_job_id = ?",
            (result["id"],),
        ).fetchall()
        self.assertEqual(len(rows), 13)
        self.assertTrue(all(row["source_kind"] == "manual" for row in rows))
        self.assertTrue(all(row["confidence"] is None for row in rows))
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM ocr_blocks WHERE recognition_job_id = ?", (result["id"],)).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM evidence_anchors").fetchone()[0],
            0,
        )

    def test_external_suggestions_are_idempotent_and_do_not_write_project_facts(self):
        fields = parse_external_contract_markdown(
            """```json
{"schemaVersion":"contract.v1","fields":{"project.name":{"value":"悦铂特项目"}}}
```"""
        )
        first = create_fallback_review(
            self.conn,
            source_job_id=self.source_job["id"],
            adapter_key="external-ai-paste",
            idempotency_key="external-fallback-1",
            fields=fields,
            actor={"id": "editor-1", "name": "刘建祥"},
            fallback_reason="external_ai",
            now=NOW,
        )
        second = create_fallback_review(
            self.conn,
            source_job_id=self.source_job["id"],
            adapter_key="external-ai-paste",
            idempotency_key="external-fallback-1",
            fields=fields,
            actor={"id": "editor-1", "name": "刘建祥"},
            fallback_reason="external_ai",
            now=NOW,
        )
        self.conn.commit()

        self.assertEqual(first["id"], second["id"])
        suggestion = self.conn.execute(
            "SELECT * FROM extracted_fields WHERE recognition_job_id = ? AND semantic_key = 'project.name'",
            (first["id"],),
        ).fetchone()
        self.assertEqual(suggestion["source_kind"], "external_ai")
        self.assertEqual(json.loads(suggestion["normalized_value_json"]), "悦铂特项目")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0], 0)

    def test_direct_manual_review_supports_proactive_fallback_without_source_job(self):
        fields = manual_contract_fields({
            "project.name": "悦铂特项目",
            "party.contractor": "江苏悦铂特建设工程有限公司",
        })

        result = create_direct_fallback_review(
            self.conn,
            document_version_id=self.source_job["document_version_id"],
            adapter_key="manual-entry",
            idempotency_key="manual-direct-1",
            fields=fields,
            actor={"id": "editor-1", "name": "刘建祥"},
            fallback_reason="manual_selected",
            now=NOW,
        )
        self.conn.commit()

        self.assertEqual(result["status"], "review_ready")
        self.assertIsNone(result["source_recognition_job_id"])
        project_name = self.conn.execute(
            "SELECT * FROM extracted_fields WHERE recognition_job_id = ? AND semantic_key = 'project.name'",
            (result["id"],),
        ).fetchone()
        self.assertEqual(project_name["source_kind"], "manual")
        self.assertEqual(json.loads(project_name["normalized_value_json"]), "悦铂特项目")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0], 0)

        provenance = self.conn.execute(
            "SELECT fallback_reason, fallback_note FROM recognition_jobs WHERE id = ?",
            (result["id"],),
        ).fetchone()
        self.assertEqual(provenance["fallback_reason"], "manual_selected")
        self.assertEqual(provenance["fallback_note"], "")

    def test_fallback_rejects_a_source_job_that_is_still_running(self):
        self.conn.execute(
            "UPDATE recognition_jobs SET status = 'running' WHERE id = ?",
            (self.source_job["id"],),
        )
        with self.assertRaisesRegex(ContractFallbackError, "当前识别状态"):
            create_fallback_review(
                self.conn,
                source_job_id=self.source_job["id"],
                adapter_key="manual-entry",
                idempotency_key="manual-fallback-invalid",
                fields=[],
                actor={"id": "editor-1", "name": "刘建祥"},
                fallback_reason="manual",
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
