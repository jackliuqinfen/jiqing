import json
import os
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import audit_api


class LifecycleApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.original_db_path = os.environ.get("AUDIT_DB_PATH")
        cls.original_upload_root = os.environ.get("UPLOAD_ROOT")
        os.environ["AUDIT_DB_PATH"] = str(Path(cls.tempdir.name) / "audit.sqlite3")
        os.environ["UPLOAD_ROOT"] = str(Path(cls.tempdir.name) / "uploads")
        audit_api.bootstrap()
        cls.server = audit_api.ThreadingHTTPServer(("127.0.0.1", 0), audit_api.Handler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.create_user("admin-user", "api-admin", "管理员", "admin")
        cls.create_user("viewer-user", "api-viewer", "只读用户", "viewer")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)
        if cls.original_db_path is None:
            os.environ.pop("AUDIT_DB_PATH", None)
        else:
            os.environ["AUDIT_DB_PATH"] = cls.original_db_path
        if cls.original_upload_root is None:
            os.environ.pop("UPLOAD_ROOT", None)
        else:
            os.environ["UPLOAD_ROOT"] = cls.original_upload_root
        cls.tempdir.cleanup()

    @classmethod
    def create_user(cls, user_id, username, display_name, role):
        with audit_api.connect() as conn:
            now = audit_api.now_iso()
            conn.execute(
                """
                INSERT INTO system_users
                (id, username, display_name, email, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, '', ?, ?, 1, ?, ?)
                """,
                (user_id, username, display_name, audit_api.hash_password("test-password"), role, now, now),
            )
            conn.commit()

    def request(self, method, path, payload=None, user_id=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if user_id:
            token = audit_api.sign_token({"sub": user_id, "exp": int(time.time()) + 300})
            headers["Authorization"] = f"Bearer {token}"
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def insert_project(self, **overrides):
        project_id = overrides.pop("id", f"project-{uuid.uuid4().hex}")
        now = audit_api.now_iso()
        values = {
            "id": project_id,
            "project_code": f"PRJ-{uuid.uuid4().hex[:8]}",
            "project_name": "生命周期 API 项目",
            "contract_date": "2026-07-11",
            "construction_unit": "施工单位",
            "owner_unit": "建设单位",
            "project_status": "awarded",
            "contract_amount": 100.0,
            "submitted_amount": 0.0,
            "created_at": now,
            "updated_at": now,
        }
        values.update(overrides)
        with audit_api.connect() as conn:
            columns = ", ".join(values)
            marks = ", ".join("?" for _ in values)
            conn.execute(
                f"INSERT INTO project_records ({columns}) VALUES ({marks})",
                tuple(values.values()),
            )
            conn.commit()
        return project_id

    def insert_contract_file(self, project_id):
        with audit_api.connect() as conn:
            conn.execute(
                """
                INSERT INTO project_files
                (id, project_id, category_key, display_name, original_name, stored_name,
                 relative_path, uploaded_at)
                VALUES (?, ?, 'contract', '合同.pdf', '合同.pdf', 'contract.pdf', 'files/contract.pdf', ?)
                """,
                (f"file-{uuid.uuid4().hex}", project_id, audit_api.now_iso()),
            )
            conn.commit()

    def insert_payment_file(self, project_id, name="银行回单.pdf"):
        file_id = f"file-{uuid.uuid4().hex}"
        with audit_api.connect() as conn:
            conn.execute(
                """
                INSERT INTO project_files
                (id, project_id, category_key, display_name, original_name, stored_name,
                 relative_path, uploaded_at)
                VALUES (?, ?, 'payment', ?, ?, 'payment.pdf', 'files/payment.pdf', ?)
                """,
                (file_id, project_id, name, name, audit_api.now_iso()),
            )
            conn.commit()
        return file_id

    def create_formal_settlement(self, project_id, contract_amount=1000000):
        status, payload = self.request(
            "POST",
            "/api/settlement/projects",
            {
                "projectId": project_id,
                "contractName": "施工合同",
                "contractAmount": contract_amount,
                "paymentTerms": "竣工验收合格后累计支付至合同付款基数的60%",
                "acceptanceStatus": "accepted",
                "acceptanceDate": "2026-07-12",
                "auditStatus": "not_submitted",
                "paymentTemplateId": "TEST",
                "paymentNodes": [
                    {
                        "nodeName": "竣工验收后付款",
                        "nodeOrder": 1,
                        "triggerCondition": "ACCEPTANCE_COMPLETED",
                        "baseType": "CONTRACT_PAYMENT_BASE",
                        "paymentRatio": 0.6,
                        "isCumulative": True,
                        "deductExisting": True,
                        "requiredDocuments": ["合同", "竣工验收证明", "付款申请单"],
                        "dueDays": 30,
                        "reminderEnabled": True,
                    }
                ],
            },
            "admin-user",
        )
        self.assertEqual(status, 201, payload)
        return payload["data"]

    def insert_audit_project(self, project_id, stage="submitted"):
        audit_id = f"audit-{uuid.uuid4().hex}"
        now = audit_api.now_iso()
        with audit_api.connect() as conn:
            project = conn.execute(
                "SELECT project_code, project_name FROM project_records WHERE id = ?",
                (project_id,),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO audit_projects
                (id, project_id, project_code, project_name, current_stage, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (audit_id, project_id, project["project_code"], project["project_name"], stage, now, now),
            )
            conn.execute(
                """
                UPDATE project_records
                SET audit_project_id = ?, audit_stage = ?
                WHERE id = ?
                """,
                (audit_id, stage, project_id),
            )
            conn.commit()
        return audit_id

    def event_count(self, project_id):
        with audit_api.connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS count FROM project_lifecycle_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()["count"]

    def system_log_count(self):
        with audit_api.connect() as conn:
            return conn.execute("SELECT COUNT(*) AS count FROM system_operation_logs").fetchone()["count"]

    def test_connect_configures_busy_timeout(self):
        with audit_api.connect() as conn:
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 5000)

    def test_snapshot_requires_authentication(self):
        project_id = self.insert_project()

        status, payload = self.request("GET", f"/api/projects/{project_id}/lifecycle")

        self.assertEqual(status, 401)
        self.assertFalse(payload["success"])
        self.assertIn("error", payload)

    def test_audit_project_list_requires_authentication(self):
        status, payload = self.request("GET", "/api/audit/projects")

        self.assertEqual(status, 401)
        self.assertFalse(payload["success"])

    def test_lifecycle_endpoints_return_404_for_a_missing_project(self):
        project_id = f"missing-{uuid.uuid4().hex}"
        requests = [
            ("GET", f"/api/projects/{project_id}/lifecycle", None),
            ("POST", f"/api/projects/{project_id}/lifecycle/validate", {"toStage": "contract_signed"}),
            ("POST", f"/api/projects/{project_id}/lifecycle/transitions", {
                "toStage": "contract_signed",
                "expectedVersion": 0,
                "idempotencyKey": "missing-project-key",
            }),
        ]

        for method, path, body in requests:
            with self.subTest(path=path):
                status, payload = self.request(method, path, body, "admin-user")

                self.assertEqual(status, 404)
                self.assertFalse(payload["success"])
                self.assertEqual(payload["code"], "project_not_found")

    def test_viewer_cannot_transition_lifecycle(self):
        project_id = self.insert_project()

        status, payload = self.request(
            "POST",
            f"/api/projects/{project_id}/lifecycle/transitions",
            {"toStage": "contract_signed", "expectedVersion": 0, "idempotencyKey": "viewer-key"},
            "viewer-user",
        )

        self.assertEqual(status, 403)
        self.assertFalse(payload["success"])

    def test_validate_returns_blockers_without_writing(self):
        project_id = self.insert_project(contract_date="", contract_amount=0, construction_unit="", owner_unit="")

        status, payload = self.request(
            "POST",
            f"/api/projects/{project_id}/lifecycle/validate",
            {"toStage": "contract_signed"},
            "admin-user",
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["currentStage"], "awarded")
        self.assertEqual(payload["data"]["currentVersion"], 0)
        self.assertEqual(payload["data"]["targetStage"], "contract_signed")
        self.assertFalse(payload["data"]["canTransition"])
        codes = {blocker["code"] for blocker in payload["data"]["blockers"]}
        self.assertIn("contract_file_required", codes)
        self.assertEqual(self.event_count(project_id), 0)

    def test_transition_returns_latest_snapshot(self):
        project_id = self.insert_project()
        self.insert_contract_file(project_id)

        status, payload = self.request(
            "POST",
            f"/api/projects/{project_id}/lifecycle/transitions",
            {"toStage": "contract_signed", "expectedVersion": 0, "idempotencyKey": "success-key"},
            "admin-user",
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["transition"]["currentStage"], "contract_signed")
        self.assertEqual(payload["data"]["snapshot"]["lifecycleVersion"], 1)
        self.assertEqual(self.event_count(project_id), 1)

    def test_transition_rejects_stale_version_with_current_version(self):
        project_id = self.insert_project(lifecycle_version=2)
        self.insert_contract_file(project_id)

        status, payload = self.request(
            "POST",
            f"/api/projects/{project_id}/lifecycle/transitions",
            {"toStage": "contract_signed", "expectedVersion": 1, "idempotencyKey": "stale-key"},
            "admin-user",
        )

        self.assertEqual(status, 409)
        self.assertEqual(payload["currentVersion"], 2)
        self.assertEqual(payload["code"], "stale_lifecycle_version")

    def test_transition_reports_gate_blockers(self):
        project_id = self.insert_project()

        status, payload = self.request(
            "POST",
            f"/api/projects/{project_id}/lifecycle/transitions",
            {"toStage": "contract_signed", "expectedVersion": 0, "idempotencyKey": "blocked-key"},
            "admin-user",
        )

        self.assertEqual(status, 422)
        self.assertFalse(payload["success"])
        self.assertIn("blockers", payload)
        self.assertEqual(payload["currentVersion"], 0)
        self.assertIn("contract_file_required", {item["code"] for item in payload["blockers"]})

    def test_transition_replay_returns_the_original_event(self):
        project_id = self.insert_project()
        self.insert_contract_file(project_id)
        request = {"toStage": "contract_signed", "expectedVersion": 0, "idempotencyKey": "replay-key"}

        first_status, first_payload = self.request("POST", f"/api/projects/{project_id}/lifecycle/transitions", request, "admin-user")
        logs_before_replay = self.system_log_count()
        replay_status, replay_payload = self.request("POST", f"/api/projects/{project_id}/lifecycle/transitions", request, "admin-user")

        self.assertEqual(first_status, 200)
        self.assertEqual(replay_status, 200)
        self.assertEqual(
            replay_payload["data"]["transition"]["event"]["id"],
            first_payload["data"]["transition"]["event"]["id"],
        )
        self.assertEqual(self.event_count(project_id), 1)
        self.assertEqual(self.system_log_count(), logs_before_replay)

    def test_transition_rejects_same_idempotency_key_for_different_target(self):
        project_id = self.insert_project()
        self.insert_contract_file(project_id)
        first = {"toStage": "contract_signed", "expectedVersion": 0, "idempotencyKey": "conflict-key"}
        conflict = {"toStage": "under_construction", "expectedVersion": 1, "idempotencyKey": "conflict-key"}
        self.request("POST", f"/api/projects/{project_id}/lifecycle/transitions", first, "admin-user")

        status, payload = self.request("POST", f"/api/projects/{project_id}/lifecycle/transitions", conflict, "admin-user")

        self.assertEqual(status, 409)
        self.assertEqual(payload["code"], "idempotency_key_conflict")
        self.assertEqual(self.event_count(project_id), 1)

    def test_direct_status_update_is_rejected(self):
        project_id = self.insert_project()

        status, payload = self.request(
            "PUT",
            f"/api/projects/{project_id}",
            {"projectStatus": "contract_signed"},
            "admin-user",
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["code"], "lifecycle_transition_required")

    def test_unchanged_project_status_allows_normal_information_update(self):
        project_id = self.insert_project()

        status, payload = self.request(
            "PUT",
            f"/api/projects/{project_id}",
            {
                "projectCode": f"UPDATED-{uuid.uuid4().hex[:8]}",
                "projectName": "允许更新的项目信息",
                "projectStatus": "awarded",
            },
            "admin-user",
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["projectStatus"], "awarded")
        self.assertEqual(payload["data"]["projectName"], "允许更新的项目信息")

    def test_update_without_status_preserves_an_advanced_lifecycle_stage_and_version(self):
        project_id = self.insert_project()
        self.insert_contract_file(project_id)
        transition_status, _ = self.request(
            "POST",
            f"/api/projects/{project_id}/lifecycle/transitions",
            {"toStage": "contract_signed", "expectedVersion": 0, "idempotencyKey": "preserve-status-key"},
            "admin-user",
        )

        self.assertEqual(transition_status, 200)
        status, payload = self.request(
            "PUT",
            f"/api/projects/{project_id}",
            {"projectCode": f"UPDATED-{uuid.uuid4().hex[:8]}", "projectName": "更新推进后的项目"},
            "admin-user",
        )

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["projectStatus"], "contract_signed")
        with audit_api.connect() as conn:
            row = conn.execute(
                "SELECT project_status, lifecycle_version FROM project_records WHERE id = ?",
                (project_id,),
            ).fetchone()
        self.assertEqual(row["project_status"], "contract_signed")
        self.assertEqual(row["lifecycle_version"], 1)

    def test_partial_project_update_preserves_audit_linkage_and_other_fields(self):
        project_id = self.insert_project(project_name="保留名称", settlement_status="not_started")
        audit_id = self.insert_audit_project(project_id)

        status, payload = self.request(
            "PUT",
            f"/api/projects/{project_id}",
            {"settlementStatus": "partially_paid"},
            "admin-user",
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["projectName"], "保留名称")
        self.assertEqual(payload["data"]["settlementStatus"], "partially_paid")
        self.assertEqual(payload["data"]["auditProjectId"], audit_id)
        self.assertEqual(payload["data"]["auditStage"], "submitted")
        with audit_api.connect() as conn:
            linked = conn.execute(
                "SELECT project_id FROM audit_projects WHERE id = ?",
                (audit_id,),
            ).fetchone()
        self.assertEqual(linked["project_id"], project_id)

    def test_generic_project_update_cannot_explicitly_clear_audit_linkage(self):
        project_id = self.insert_project(project_name="受保护关联")
        audit_id = self.insert_audit_project(project_id)

        status, payload = self.request(
            "PUT",
            f"/api/projects/{project_id}",
            {"projectName": "受保护关联", "auditProjectId": "", "auditStage": "not_linked"},
            "admin-user",
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["code"], "audit_linkage_managed")
        with audit_api.connect() as conn:
            project = conn.execute(
                "SELECT audit_project_id, audit_stage FROM project_records WHERE id = ?",
                (project_id,),
            ).fetchone()
            audit = conn.execute(
                "SELECT project_id FROM audit_projects WHERE id = ?",
                (audit_id,),
            ).fetchone()
        self.assertEqual(project["audit_project_id"], audit_id)
        self.assertEqual(project["audit_stage"], "submitted")
        self.assertEqual(audit["project_id"], project_id)

    def test_standard_project_creation_is_blocked_until_contract_review_is_confirmed(self):
        status, payload = self.request(
            "POST",
            "/api/projects",
            {"projectCode": f"NEW-{uuid.uuid4().hex[:8]}", "projectName": "普通新建项目"},
            "admin-user",
        )

        self.assertEqual(status, 409)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], "contract_review_required")
        self.assertIn("上传合同", payload["error"])

    def test_start_audit_before_pending_submission_is_rejected(self):
        project_id = self.insert_project(submitted_amount=100)

        status, payload = self.request(
            "POST",
            f"/api/projects/{project_id}/start-audit",
            {},
            "admin-user",
        )

        self.assertEqual(status, 422)
        self.assertIn("audit_stage_not_reached", {item["code"] for item in payload["blockers"]})
        with audit_api.connect() as conn:
            audit_count = conn.execute(
                "SELECT COUNT(*) AS count FROM audit_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()["count"]
        self.assertEqual(audit_count, 0)

    def test_concurrent_audit_start_creates_only_one_audit_project(self):
        project_id = self.insert_project(project_status="pending_submission", submitted_amount=100)
        barrier = threading.Barrier(2)

        def start_audit():
            barrier.wait(timeout=3)
            return self.request(
                "POST",
                f"/api/projects/{project_id}/start-audit",
                {},
                "admin-user",
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: start_audit(), range(2)))

        self.assertEqual(sorted(status for status, _payload in results), [201, 409])
        with audit_api.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM audit_projects WHERE project_id = ? AND status != 'deleted'",
                (project_id,),
            ).fetchall()
        self.assertEqual(len(rows), 1)

    def test_audit_progress_rejects_stage_skips_and_advances_project_lifecycle(self):
        project_id = self.insert_project(
            project_status="pending_submission",
            submitted_amount=100,
            lifecycle_version=4,
        )
        audit_id = self.insert_audit_project(project_id, "submitted")

        skipped_status, skipped_payload = self.request(
            "POST",
            f"/api/audit/projects/{audit_id}/progress",
            {"stageCode": "archived"},
            "admin-user",
        )
        self.assertEqual(skipped_status, 422)
        self.assertEqual(skipped_payload["code"], "audit_stage_transition_required")

        status, payload = self.request(
            "POST",
            f"/api/audit/projects/{audit_id}/progress",
            {"stageCode": "first_audit"},
            "admin-user",
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["stage"], "first_audit")
        with audit_api.connect() as conn:
            project = conn.execute(
                "SELECT project_status, lifecycle_version, audit_stage FROM project_records WHERE id = ?",
                (project_id,),
            ).fetchone()
            event = conn.execute(
                "SELECT from_stage, to_stage FROM project_lifecycle_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        self.assertEqual(project["project_status"], "first_audit")
        self.assertEqual(project["audit_stage"], "first_audit")
        self.assertEqual(project["lifecycle_version"], 5)
        self.assertEqual((event["from_stage"], event["to_stage"]), ("pending_submission", "first_audit"))

        replay_status, replay_payload = self.request(
            "POST",
            f"/api/audit/projects/{audit_id}/progress",
            {"stageCode": "first_audit"},
            "admin-user",
        )
        self.assertEqual(replay_status, 200)
        self.assertEqual(replay_payload["data"]["stage"], "first_audit")
        with audit_api.connect() as conn:
            event_count = conn.execute(
                "SELECT COUNT(*) AS count FROM project_lifecycle_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()["count"]
            stage_count = conn.execute(
                "SELECT COUNT(*) AS count FROM audit_project_stages WHERE project_id = ?",
                (audit_id,),
            ).fetchone()["count"]
        self.assertEqual(event_count, 1)
        self.assertEqual(stage_count, 1)

    def test_project_lifecycle_cannot_bypass_linked_audit_progress(self):
        project_id = self.insert_project(
            project_status="pending_submission",
            submitted_amount=100,
            lifecycle_version=4,
        )
        audit_id = self.insert_audit_project(project_id, "submitted")

        status, payload = self.request(
            "POST",
            f"/api/projects/{project_id}/lifecycle/transitions",
            {"toStage": "first_audit", "expectedVersion": 4, "idempotencyKey": "bypass-audit"},
            "admin-user",
        )

        self.assertEqual(status, 422)
        self.assertIn("audit_progress_required", {item["code"] for item in payload["blockers"]})
        with audit_api.connect() as conn:
            project = conn.execute(
                "SELECT project_status FROM project_records WHERE id = ?",
                (project_id,),
            ).fetchone()
            audit = conn.execute(
                "SELECT current_stage FROM audit_projects WHERE id = ?",
                (audit_id,),
            ).fetchone()
        self.assertEqual(project["project_status"], "pending_submission")
        self.assertEqual(audit["current_stage"], "submitted")

    def test_settlement_cannot_claim_facts_beyond_project_lifecycle(self):
        project_id = self.insert_project(project_status="awarded")

        status, payload = self.request(
            "POST",
            "/api/settlement/projects",
            {
                "projectId": project_id,
                "contractAmount": 100,
                "acceptanceStatus": "accepted",
                "acceptanceDate": "2026-07-12",
                "auditStatus": "submitted",
                "submittedAmount": 100,
            },
            "admin-user",
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["code"], "settlement_stage_conflict")

    def test_settlement_bank_receipt_requires_evidence_and_updates_real_totals(self):
        project_id = self.insert_project(project_status="completed_acceptance", contract_amount=1000000)
        settlement = self.create_formal_settlement(project_id)
        status, application_payload = self.request(
            "POST",
            "/api/settlement/payment-applications",
            {
                "settlementId": settlement["id"],
                "applicationName": "竣工验收后第一次付款申请",
                "appliedAmount": 600000,
                "submittedDate": "2026-07-13",
                "approvalStatus": "APPROVED",
                "approvedAmount": 500000,
                "approvalDate": "2026-07-15",
            },
            "admin-user",
        )
        self.assertEqual(status, 201, application_payload)
        application_id = application_payload["data"]["id"]

        status, missing_evidence = self.request(
            "POST",
            "/api/settlement/receipts",
            {
                "settlementId": settlement["id"],
                "receiptType": "BANK_TRANSFER",
                "amount": 200000,
                "receivedDate": "2026-07-16",
                "payerName": "建设单位",
                "receivingEntity": "施工单位",
                "receivingAccount": "测试账户",
                "allocations": [{"applicationId": application_id, "allocationAmount": 200000}],
            },
            "admin-user",
        )
        self.assertEqual(status, 400)
        self.assertIn("凭证", missing_evidence["error"])

        payment_file_id = self.insert_payment_file(project_id)
        status, duplicate_allocation = self.request(
            "POST",
            "/api/settlement/receipts",
            {
                "settlementId": settlement["id"],
                "receiptType": "BANK_TRANSFER",
                "amount": 600000,
                "receivedDate": "2026-07-16",
                "payerName": "建设单位",
                "receivingEntity": "施工单位",
                "receivingAccount": "测试账户",
                "attachmentFileId": payment_file_id,
                "allocations": [
                    {"applicationId": application_id, "allocationAmount": 300000},
                    {"applicationId": application_id, "allocationAmount": 300000},
                ],
            },
            "admin-user",
        )
        self.assertEqual(status, 400)
        self.assertIn("剩余审批金额", duplicate_allocation["error"])

        status, receipt_payload = self.request(
            "POST",
            "/api/settlement/receipts",
            {
                "settlementId": settlement["id"],
                "receiptType": "BANK_TRANSFER",
                "amount": 200000,
                "receivedDate": "2026-07-16",
                "payerName": "建设单位",
                "receivingEntity": "施工单位",
                "receivingAccount": "测试账户",
                "attachmentFileId": payment_file_id,
                "allocations": [{"applicationId": application_id, "allocationAmount": 200000}],
            },
            "admin-user",
        )
        self.assertEqual(status, 201, receipt_payload)

        status, projects_payload = self.request("GET", "/api/settlement/projects", user_id="admin-user")
        self.assertEqual(status, 200)
        current = next(item for item in projects_payload["data"] if item["id"] == settlement["id"])
        self.assertEqual(current["paymentSummary"]["ownerPaidAmount"], 200000)
        self.assertEqual(current["paymentSummary"]["bankReceivedAmount"], 200000)
        self.assertEqual(current["paymentSummary"]["approvedUnreceivedAmount"], 300000)

    def test_payment_application_can_record_owner_approval_result(self):
        project_id = self.insert_project(project_status="completed_acceptance", contract_amount=1000000)
        settlement = self.create_formal_settlement(project_id)
        status, application_payload = self.request(
            "POST",
            "/api/settlement/payment-applications",
            {
                "settlementId": settlement["id"],
                "applicationName": "竣工验收付款申请",
                "appliedAmount": 600000,
                "submittedDate": "2026-07-13",
                "approvalStatus": "SUBMITTED",
            },
            "admin-user",
        )
        self.assertEqual(status, 201, application_payload)
        status, update_payload = self.request(
            "PUT",
            f"/api/settlement/payment-applications/{application_payload['data']['id']}/status",
            {
                "approvalStatus": "APPROVED",
                "approvedAmount": 500000,
                "approvalDate": "2026-07-15",
            },
            "admin-user",
        )
        self.assertEqual(status, 200, update_payload)
        self.assertEqual(update_payload["data"]["approvalStatus"], "APPROVED")
        self.assertEqual(update_payload["data"]["approvedAmount"], 500000)

    def test_acceptance_counts_as_owner_paid_but_not_bank_received(self):
        project_id = self.insert_project(project_status="completed_acceptance", contract_amount=1000000)
        settlement = self.create_formal_settlement(project_id)
        status, application_payload = self.request(
            "POST",
            "/api/settlement/payment-applications",
            {
                "settlementId": settlement["id"],
                "applicationName": "竣工验收付款申请",
                "appliedAmount": 300000,
                "submittedDate": "2026-07-13",
                "approvalStatus": "APPROVED",
                "approvedAmount": 300000,
                "approvalDate": "2026-07-15",
            },
            "admin-user",
        )
        self.assertEqual(status, 201, application_payload)
        payment_file_id = self.insert_payment_file(project_id, "电子承兑汇票.pdf")
        status, receipt_payload = self.request(
            "POST",
            "/api/settlement/receipts",
            {
                "settlementId": settlement["id"],
                "receiptType": "BANK_ACCEPTANCE",
                "amount": 300000,
                "receivedDate": "2026-07-16",
                "payerName": "建设单位",
                "attachmentFileId": payment_file_id,
                "acceptanceNumber": f"AC-{uuid.uuid4().hex[:10]}",
                "acceptorName": "测试银行",
                "issuerName": "建设单位",
                "issueDate": "2026-07-16",
                "dueDate": "2026-12-16",
                "draftMedium": "电子",
                "holderName": "施工单位",
                "allocations": [{"applicationId": application_payload["data"]["id"], "allocationAmount": 300000}],
            },
            "admin-user",
        )
        self.assertEqual(status, 201, receipt_payload)
        self.assertEqual(receipt_payload["data"]["acceptanceStatus"], "OUTSTANDING")

        status, projects_payload = self.request("GET", "/api/settlement/projects", user_id="admin-user")
        self.assertEqual(status, 200)
        current = next(item for item in projects_payload["data"] if item["id"] == settlement["id"])
        self.assertEqual(current["paymentSummary"]["ownerPaidAmount"], 300000)
        self.assertEqual(current["paymentSummary"]["bankReceivedAmount"], 0)
        self.assertEqual(current["paymentSummary"]["outstandingAcceptanceAmount"], 300000)
        self.assertEqual(current["paymentSummary"]["collectionStatus"], "已全部收到，承兑汇票待兑付")

        status, update_payload = self.request(
            "PUT",
            f"/api/settlement/receipts/{receipt_payload['data']['id']}/status",
            {"acceptanceStatus": "REFUSED_RETURNED", "disposedDate": "2026-12-17", "remark": "承兑汇票退回"},
            "admin-user",
        )
        self.assertEqual(status, 200, update_payload)
        status, projects_payload = self.request("GET", "/api/settlement/projects", user_id="admin-user")
        current = next(item for item in projects_payload["data"] if item["id"] == settlement["id"])
        self.assertEqual(current["paymentSummary"]["ownerPaidAmount"], 0)
        self.assertEqual(current["paymentSummary"]["outstandingAcceptanceAmount"], 0)
        self.assertEqual(current["paymentSummary"]["refusedAmount"], 300000)
        self.assertEqual(current["paymentSummary"]["approvedUnreceivedAmount"], 300000)

    def test_backfill_only_copies_direct_semantically_matching_facts(self):
        audit_id = f"audit-{uuid.uuid4().hex}"
        with audit_api.connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_projects
                (id, project_code, project_name, audited_unit, second_audit_department, contractor_name,
                 submitted_amount, current_stage, doc_status, start_date, submit_date,
                 audit_deadline, status, created_at, updated_at)
                VALUES (?, 'HISTORY-001', '历史审计项目', '审计单位', '复审部门', '施工联系人',
                        88, 'first_audit', '资料齐全', '2026-01-01', '2026-02-01',
                        '2026-03-01', 'active', '', '')
                """,
                (audit_id,),
            )
            audit_api.backfill_project_records(conn)
            conn.commit()
            backfilled = conn.execute(
                """
                SELECT construction_unit, owner_unit, company_role, manager_name,
                       contract_amount, submitted_amount, paid_amount, payment_terms,
                       settlement_status, audit_stage, planned_start_date, planned_end_date,
                       document_completion, missing_required_count, settlement_book_status,
                       first_audit_material_status, second_audit_material_status,
                       variation_count, variation_amount, created_at, updated_at, project_status
                FROM project_records
                WHERE audit_project_id = ?
                """,
                (audit_id,),
            ).fetchone()

        self.assertEqual(backfilled["construction_unit"], "")
        self.assertEqual(backfilled["owner_unit"], "")
        self.assertEqual(backfilled["company_role"], "")
        self.assertEqual(backfilled["manager_name"], "")
        self.assertEqual(backfilled["payment_terms"], "")
        self.assertIsNone(backfilled["contract_amount"])
        self.assertEqual(backfilled["submitted_amount"], 88)
        self.assertIsNone(backfilled["paid_amount"])
        self.assertEqual(backfilled["settlement_status"], "")
        self.assertEqual(backfilled["audit_stage"], "first_audit")
        self.assertEqual(backfilled["project_status"], "first_audit")
        self.assertEqual(backfilled["planned_start_date"], "")
        self.assertEqual(backfilled["planned_end_date"], "")
        self.assertIsNone(backfilled["document_completion"])
        self.assertIsNone(backfilled["missing_required_count"])
        self.assertEqual(backfilled["settlement_book_status"], "")
        self.assertEqual(backfilled["first_audit_material_status"], "")
        self.assertEqual(backfilled["second_audit_material_status"], "")
        self.assertIsNone(backfilled["variation_count"])
        self.assertIsNone(backfilled["variation_amount"])
        self.assertEqual(backfilled["created_at"], "")
        self.assertEqual(backfilled["updated_at"], "")


if __name__ == "__main__":
    unittest.main()
