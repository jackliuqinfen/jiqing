import json
import io
import os
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from server import audit_api
from server.document_repository import (
    add_document_pages,
    create_document_upload,
    create_recognition_job,
)
from server.document_review_service import open_review


CONTRACT_FIELDS = {
    "project.name": "API 契约测试工程",
    "party.owner": "建设单位",
    "party.contractor": "江苏悦铂特建设工程有限公司",
    "contract.amount": 100_000_000,
    "contract.signed_date": "2026-07-01",
    "contract.payment_terms": ["竣工验收后支付60%"],
}


class DocumentApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tempdir.name)
        cls.original_db_path = os.environ.get("AUDIT_DB_PATH")
        cls.original_upload_root = os.environ.get("UPLOAD_ROOT")
        os.environ["AUDIT_DB_PATH"] = str(cls.root / "audit.sqlite3")
        os.environ["UPLOAD_ROOT"] = str(cls.root / "uploads")
        audit_api.bootstrap()

        cls.project_scopes = {
            "admin-user": {"project-allowed"},
            "editor-user": {"project-allowed"},
            "viewer-user": {"project-allowed"},
            "outsider-user": {"project-other"},
        }

        class ContractHandler(audit_api.Handler):
            document_max_upload_size = staticmethod(audit_api.max_upload_size)

            @staticmethod
            def document_project_scope_provider(_conn, actor):
                return cls.project_scopes.get(actor["id"], set())

        cls.handler_class = ContractHandler
        cls.server = audit_api.ThreadingHTTPServer(("127.0.0.1", 0), ContractHandler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

        cls._create_user("admin-user", "document-admin", "文档管理员", "admin")
        cls._create_user("editor-user", "document-editor", "文档编辑", "editor")
        cls._create_user("viewer-user", "document-viewer", "文档只读", "viewer")
        cls._create_user("outsider-user", "document-outsider", "范围外用户", "editor")
        cls._create_project("project-allowed", "DOC-ALLOWED")
        cls._create_project("project-other", "DOC-OTHER")

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
    def _create_user(cls, user_id, username, display_name, role):
        with audit_api.connect() as conn:
            now = audit_api.now_iso()
            conn.execute(
                """
                INSERT INTO system_users
                (id, username, display_name, email, password_hash, role, is_active,
                 created_at, updated_at)
                VALUES (?, ?, ?, '', ?, ?, 1, ?, ?)
                """,
                (
                    user_id,
                    username,
                    display_name,
                    audit_api.hash_password("test-password"),
                    role,
                    now,
                    now,
                ),
            )

    @classmethod
    def _create_project(cls, project_id, project_code):
        with audit_api.connect() as conn:
            now = audit_api.now_iso()
            conn.execute(
                """
                INSERT INTO project_records
                (id, project_code, project_name, project_status, lifecycle_version,
                 created_at, updated_at)
                VALUES (?, ?, ?, 'contract_signed', 0, ?, ?)
                """,
                (project_id, project_code, f"项目 {project_code}", now, now),
            )

    def token(self, user_id):
        return audit_api.sign_token({"sub": user_id, "exp": int(time.time()) + 300})

    def request(self, method, path, *, payload=None, body=None, headers=None, user_id=None):
        request_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        if user_id:
            request_headers["Authorization"] = f"Bearer {self.token(user_id)}"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                response_body = response.read()
                return response.status, dict(response.headers), self._decode(response_body, response.headers)
        except HTTPError as error:
            with error:
                response_body = error.read()
                return error.code, dict(error.headers), self._decode(response_body, error.headers)

    @staticmethod
    def _decode(body, headers):
        if "application/json" in headers.get("Content-Type", ""):
            return json.loads(body.decode("utf-8"))
        return body

    def upload(self, *, user_id="editor-user", fields=None, filename="document.pdf", content=b"%PDF-1.7\napi"):
        boundary = f"----document-api-{uuid.uuid4().hex}"
        parts = []
        values = {
            "documentType": "construction_contract",
            "lifecycleStage": "contract_handoff",
            **(fields or {}),
        }
        for key, value in values.items():
            parts.extend([
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("ascii"),
                str(value).encode("utf-8"),
                b"\r\n",
            ])
        parts.extend([
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
            b"Content-Type: application/octet-stream\r\n\r\n",
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ])
        return self.request(
            "POST",
            "/api/documents/uploads",
            body=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            user_id=user_id,
        )

    @staticmethod
    def one_page_pdf():
        output = io.BytesIO()
        image = Image.new("RGB", (600, 840), "white")
        image.save(output, format="PDF", resolution=72)
        image.close()
        return output.getvalue()

    def create_document(self, *, project_id="project-allowed", content=None):
        content = self.one_page_pdf() if content is None else content
        digest = uuid.uuid4().hex
        relative_path = f"documents/contract-{digest}.pdf"
        path = Path(os.environ["UPLOAD_ROOT"]) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        with audit_api.connect() as conn:
            created = create_document_upload(
                conn,
                document_type="construction_contract",
                lifecycle_stage="contract_handoff",
                project_id=project_id,
                original_name="施工合同.pdf",
                mime_type="application/pdf",
                file_size=len(content),
                sha256=digest,
                relative_path=relative_path,
                uploaded_by="editor-user",
            )
        return created

    def add_page(self, created, content=b"0123456789"):
        relative_path = f"documents/pages/{uuid.uuid4().hex}.png"
        path = Path(os.environ["UPLOAD_ROOT"]) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        with audit_api.connect() as conn:
            return add_document_pages(
                conn,
                document_version_id=created["version"]["id"],
                pages=[{
                    "page_number": 1,
                    "relative_path": relative_path,
                    "width_px": 100,
                    "height_px": 200,
                    "dpi": 300,
                    "rotation_degrees": 0,
                    "quality_score": 0.9,
                    "preprocessing_version": "test-v1",
                }],
            )[0]

    def create_job(self, created, *, status="queued", key=None):
        with audit_api.connect() as conn:
            job = create_recognition_job(
                conn,
                document_version_id=created["version"]["id"],
                adapter_key="manual-v1",
                schema_version="contract.v1",
                idempotency_key=key or f"recognize:{uuid.uuid4().hex}",
            )
            if status != "queued":
                conn.execute(
                    "UPDATE recognition_jobs SET status = ? WHERE id = ?",
                    (status, job["id"]),
                )
                job = dict(conn.execute("SELECT * FROM recognition_jobs WHERE id = ?", (job["id"],)).fetchone())
        return job

    def create_review(self, fields):
        created = self.create_document(project_id=None)
        page = self.add_page(created)
        job = self.create_job(created, status="review_ready")
        with audit_api.connect() as conn:
            conn.execute(
                "UPDATE documents SET status = 'review_ready' WHERE id = ?",
                (created["document"]["id"],),
            )
            for index, (semantic_key, normalized_value) in enumerate(fields.items(), start=1):
                field_id = f"field-{uuid.uuid4().hex}"
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
                        audit_api.now_iso(),
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
                        f"anchor-{uuid.uuid4().hex}",
                        field_id,
                        created["version"]["id"],
                        page["id"],
                        str(normalized_value),
                        audit_api.now_iso(),
                    ),
                )
            conn.commit()
            review = open_review(
                conn,
                document_id=created["document"]["id"],
                recognition_job_id=job["id"],
                actor={"id": "editor-user", "name": "文档编辑"},
                allowed_project_ids=(),
            )
        return created, page, job, review

    def assert_no_internal_fields(self, payload):
        forbidden = {
            "relative_path",
            "relativePath",
            "provider_metadata_json",
            "providerMetadata",
            "provider_request_id",
            "providerRequestId",
            "raw_payload",
            "rawPayload",
            "metadata_json",
        }

        def visit(value):
            if isinstance(value, dict):
                self.assertTrue(forbidden.isdisjoint(value), forbidden.intersection(value))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload)

    def test_all_document_and_intake_routes_require_authentication(self):
        requests = [
            ("POST", "/api/documents/uploads"),
            ("GET", "/api/documents/document-id"),
            ("GET", "/api/document-versions/version-id/pages/1/image"),
            ("POST", "/api/document-recognition-jobs"),
            ("GET", "/api/document-recognition-jobs/job-id"),
            ("POST", "/api/document-recognition-jobs/job-id/retry"),
            ("GET", "/api/document-reviews/review-id"),
            ("POST", "/api/document-reviews/review-id/decisions"),
            ("POST", "/api/document-reviews/review-id/confirm"),
            ("POST", "/api/document-versions/version-id/manual-review"),
            ("POST", "/api/document-versions/version-id/external-import"),
            ("POST", "/api/document-recognition-jobs/job-id/manual-review"),
            ("POST", "/api/document-recognition-jobs/job-id/external-import"),
            ("GET", "/api/project-intake-drafts"),
            ("POST", "/api/project-intake-drafts"),
            ("GET", "/api/project-intake-drafts/draft-id"),
            ("POST", "/api/project-intake-drafts/draft-id"),
            ("POST", "/api/project-intake-drafts/draft-id/abandon"),
        ]

        for method, path in requests:
            with self.subTest(method=method, path=path):
                status, _headers, payload = self.request(method, path)
                self.assertEqual(status, 401)
                self.assertFalse(payload["success"])

    def test_unbound_documents_are_owner_scoped_and_viewer_write_routes_return_403(self):
        created, _page, job, review = self.create_review({"project.name": "缺字段合同"})
        read_paths = [
            f"/api/documents/{created['document']['id']}",
            f"/api/document-recognition-jobs/{job['id']}",
            f"/api/document-reviews/{review['id']}",
        ]
        for path in read_paths:
            with self.subTest(path=path):
                status, _headers, payload = self.request("GET", path, user_id="editor-user")
                self.assertEqual(status, 200)
                self.assert_no_internal_fields(payload)
                forbidden_status, _headers, forbidden = self.request(
                    "GET", path, user_id="viewer-user"
                )
                self.assertEqual(forbidden_status, 403)
                self.assertEqual(forbidden["code"], "unbound_document_forbidden")

        writes = [
            ("POST", "/api/documents/uploads", None),
            ("POST", "/api/document-recognition-jobs", {}),
            ("POST", f"/api/document-recognition-jobs/{job['id']}/retry", {}),
            ("POST", f"/api/document-reviews/{review['id']}/decisions", {}),
            ("POST", f"/api/document-reviews/{review['id']}/confirm", {}),
            ("POST", "/api/project-intake-drafts", {}),
            ("POST", f"/api/document-recognition-jobs/{job['id']}/manual-review", {}),
        ]
        for method, path, payload in writes:
            with self.subTest(path=path):
                status, _headers, _payload = self.request(
                    method, path, payload=payload, user_id="viewer-user"
                )
                self.assertEqual(status, 403)

        status, _headers, payload = self.upload(
            user_id="admin-user",
            content=b"%PDF-1.7\nadmin-write",
        )
        self.assertEqual(status, 201)
        self.assertFalse(payload["data"]["replayed"])

    def test_injected_project_scope_blocks_upload_and_existing_resources(self):
        created = self.create_document(project_id="project-allowed")

        status, _headers, payload = self.request(
            "GET",
            f"/api/documents/{created['document']['id']}",
            user_id="outsider-user",
        )
        self.assertEqual(status, 403)
        self.assertFalse(payload["success"])

    def test_production_default_scope_is_admin_only_until_project_grants_are_configured(self):
        self.assertIsNone(
            audit_api.Handler.document_project_scope_provider(
                None, {"id": "admin-user", "role": "admin"}
            )
        )
        self.assertEqual(
            audit_api.Handler.document_project_scope_provider(
                None, {"id": "editor-user", "role": "editor"}
            ),
            set(),
        )

    def test_document_json_routes_reject_oversized_bodies(self):
        body = b"{" + b'"padding":"' + b"x" * (2 * 1024 * 1024) + b'"}'
        status, _headers, payload = self.request(
            "POST",
            "/api/document-recognition-jobs",
            body=body,
            headers={"Content-Type": "application/json"},
            user_id="editor-user",
        )

        self.assertEqual(status, 413)
        self.assertEqual(payload["code"], "json_body_too_large")

        status, _headers, payload = self.upload(
            user_id="outsider-user",
            fields={"projectId": "project-allowed"},
        )
        self.assertEqual(status, 403)
        self.assertFalse(payload["success"])

    def test_upload_validates_five_signatures_and_replays_same_scope_hash(self):
        samples = [
            ("contract.pdf", b"%PDF-1.7\ncontract", "application/pdf"),
            ("scan.png", b"\x89PNG\r\n\x1a\nscan", "image/png"),
            ("scan.jpg", b"\xff\xd8\xff\xe0jpeg", "image/jpeg"),
            ("scan.tiff", b"II*\x00tiff", "image/tiff"),
            ("scan.webp", b"RIFF\x04\x00\x00\x00WEBPwebp", "image/webp"),
        ]
        first_payload = None
        for filename, content, mime_type in samples:
            with self.subTest(filename=filename):
                status, _headers, payload = self.upload(filename=filename, content=content)
                self.assertEqual(status, 201)
                self.assertEqual(payload["data"]["version"]["mimeType"], mime_type)
                self.assert_no_internal_fields(payload)
                if first_payload is None:
                    first_payload = payload

        before = len([path for path in Path(os.environ["UPLOAD_ROOT"]).rglob("*") if path.is_file()])
        status, _headers, replay = self.upload(
            filename="renamed.pdf",
            content=samples[0][1],
        )
        after = len([path for path in Path(os.environ["UPLOAD_ROOT"]).rglob("*") if path.is_file()])
        self.assertEqual(status, 200)
        self.assertTrue(replay["data"]["replayed"])
        self.assertEqual(replay["data"]["document"]["id"], first_payload["data"]["document"]["id"])
        self.assertEqual(after, before)

    def test_contract_upload_rejects_existing_or_candidate_project_association(self):
        before = len([path for path in Path(os.environ["UPLOAD_ROOT"]).rglob("*") if path.is_file()])
        for field_name in ("projectId", "candidateProjectId"):
            with self.subTest(field_name=field_name):
                status, _headers, payload = self.upload(
                    fields={field_name: "project-allowed"},
                    content=b"%PDF-1.7\ncontract-association-forbidden",
                )
                self.assertEqual(status, 422)
                self.assertEqual(payload["code"], "contract_project_association_forbidden")
        after = len([path for path in Path(os.environ["UPLOAD_ROOT"]).rglob("*") if path.is_file()])
        self.assertEqual(after, before)

    def test_phase_one_upload_rejects_deferred_document_types(self):
        status, _headers, payload = self.upload(
            fields={
                "documentType": "completion_acceptance_certificate",
                "lifecycleStage": "acceptance",
            },
            content=b"%PDF-1.7\ndeferred-acceptance-certificate",
        )

        self.assertEqual(status, 422)
        self.assertEqual(payload["code"], "phase_one_contract_only")

    def test_concurrent_same_scope_uploads_create_once_and_replay_once(self):
        barrier = threading.Barrier(3)
        results = []

        def upload_once():
            barrier.wait()
            results.append(
                self.upload(
                    filename="concurrent-contract.pdf",
                    content=b"%PDF-1.7\nconcurrent-contract-content",
                )
            )

        workers = [threading.Thread(target=upload_once) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(timeout=10)

        self.assertEqual(len(results), 2)
        self.assertEqual(sorted(item[0] for item in results), [200, 201])
        document_ids = {item[2]["data"]["document"]["id"] for item in results}
        self.assertEqual(len(document_ids), 1)

    def test_upload_rejects_spoofed_type_and_oversize_without_partial_files(self):
        status, _headers, payload = self.upload(
            filename="fake.pdf",
            content=b"not-a-supported-file",
        )
        self.assertEqual(status, 422)
        self.assertEqual(payload["code"], "unsupported_document_signature")

        self.handler_class.document_max_upload_size = staticmethod(lambda: 64)
        before = len([path for path in Path(os.environ["UPLOAD_ROOT"]).rglob("*") if path.is_file()])
        try:
            status, _headers, payload = self.upload(content=b"%PDF-" + b"x" * 128)
        finally:
            self.handler_class.document_max_upload_size = staticmethod(audit_api.max_upload_size)
        after = len([path for path in Path(os.environ["UPLOAD_ROOT"]).rglob("*") if path.is_file()])

        self.assertEqual(status, 413)
        self.assertEqual(payload["code"], "upload_too_large")
        self.assertEqual(after, before)

    def test_recognition_create_poll_and_retry_are_whitelisted(self):
        created = self.create_document()
        status, _headers, created_payload = self.request(
            "POST",
            "/api/document-recognition-jobs",
            payload={
                "documentVersionId": created["version"]["id"],
                "adapterKey": "manual-v1",
                "schemaVersion": "contract.v1",
                "idempotencyKey": f"api:{uuid.uuid4().hex}",
            },
            user_id="editor-user",
        )
        self.assertEqual(status, 201)
        job_id = created_payload["data"]["id"]
        self.assertEqual(created_payload["data"]["adapterKey"], "manual")

        status, _headers, polled = self.request(
            "GET",
            f"/api/document-recognition-jobs/{job_id}",
            user_id="viewer-user",
        )
        self.assertEqual(status, 200)
        self.assertEqual(polled["data"]["id"], job_id)
        self.assert_no_internal_fields(polled)

        with audit_api.connect() as conn:
            conn.execute("UPDATE recognition_jobs SET status = 'failed' WHERE id = ?", (job_id,))
        with patch(
            "server.audit_api.build_recognition_adapter",
            return_value=SimpleNamespace(adapter_key="provider-v2"),
        ):
            status, _headers, retried = self.request(
                "POST",
                f"/api/document-recognition-jobs/{job_id}/retry",
                payload={"idempotencyKey": f"retry:{uuid.uuid4().hex}"},
                user_id="editor-user",
            )
        self.assertEqual(status, 201)
        self.assertEqual(retried["data"]["status"], "queued")
        self.assertEqual(retried["data"]["adapterKey"], "provider-v2")
        self.assertNotEqual(retried["data"]["id"], job_id)

    def test_start_recognition_renders_uploaded_pdf_pages_at_300_dpi(self):
        status, _headers, uploaded = self.upload(content=self.one_page_pdf())
        self.assertEqual(status, 201)

        status, _headers, created_job = self.request(
            "POST",
            "/api/document-recognition-jobs",
            payload={
                "documentVersionId": uploaded["data"]["version"]["id"],
                "adapterKey": "manual",
                "schemaVersion": "contract.v1",
                "idempotencyKey": f"render:{uuid.uuid4().hex}",
            },
            user_id="editor-user",
        )
        self.assertEqual(status, 201)
        self.assertEqual(created_job["data"]["status"], "queued")

        status, _headers, document = self.request(
            "GET",
            f"/api/documents/{uploaded['data']['document']['id']}",
            user_id="editor-user",
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(document["data"]["pages"]), 1)
        self.assertEqual(document["data"]["pages"][0]["dpi"], 300)
        self.assertGreater(document["data"]["pages"][0]["width"], 0)
        self.assertGreater(document["data"]["pages"][0]["height"], 0)

    def test_recognition_poll_exposes_review_id_when_review_is_ready(self):
        _created, _page, job, review = self.create_review(CONTRACT_FIELDS)

        status, _headers, payload = self.request(
            "GET",
            f"/api/document-recognition-jobs/{job['id']}",
            user_id="editor-user",
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status"], "review_ready")
        self.assertEqual(payload["data"]["reviewStatus"], "open")
        self.assertEqual(payload["data"]["reviewId"], review["id"])
        self.assert_no_internal_fields(payload)

    def test_owner_scoped_intake_drafts_never_create_project_records(self):
        with audit_api.connect() as conn:
            before_projects = conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0]

        status, _headers, created = self.request(
            "POST",
            "/api/project-intake-drafts",
            payload={
                "values": {"project.name": "悦铂特项目"},
                "fallbackReason": "manual_selected",
                "fallbackNote": "合同扫描件暂未上传",
            },
            user_id="editor-user",
        )
        self.assertEqual(status, 201, created)
        draft_id = created["data"]["id"]

        status, _headers, listed = self.request(
            "GET", "/api/project-intake-drafts", user_id="editor-user"
        )
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in listed["data"]], [draft_id])

        status, _headers, outsider_list = self.request(
            "GET", "/api/project-intake-drafts", user_id="outsider-user"
        )
        self.assertEqual(status, 200)
        self.assertNotIn(draft_id, [item["id"] for item in outsider_list["data"]])

        status, _headers, updated = self.request(
            "POST",
            f"/api/project-intake-drafts/{draft_id}",
            payload={"values": {"project.name": "悦铂特工程"}},
            user_id="editor-user",
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["data"]["values"]["project.name"], "悦铂特工程")

        status, _headers, abandoned = self.request(
            "POST",
            f"/api/project-intake-drafts/{draft_id}/abandon",
            payload={},
            user_id="editor-user",
        )
        self.assertEqual(status, 200)
        self.assertEqual(abandoned["data"]["status"], "abandoned")
        with audit_api.connect() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0],
                before_projects,
            )

    def test_proactive_manual_and_external_import_open_review_without_fake_project(self):
        with audit_api.connect() as conn:
            before_projects = conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0]
        for mode in ("manual-review", "external-import"):
            with self.subTest(mode=mode):
                status, _headers, uploaded = self.upload(
                    content=self.one_page_pdf() + uuid.uuid4().hex.encode("ascii"),
                    filename=f"{mode}.pdf",
                )
                self.assertEqual(status, 201)
                version_id = uploaded["data"]["version"]["id"]
                payload = {
                    "idempotencyKey": f"{mode}:{uuid.uuid4().hex}",
                    "fallbackReason": f"{mode}_selected",
                }
                if mode == "manual-review":
                    payload["values"] = {"project.name": "悦铂特项目"}
                else:
                    payload["markdown"] = """```json
{"schemaVersion":"contract.v1","fields":{"project.name":{"value":"悦铂特项目","evidence":"项目名称：悦铂特项目","page":1}}}
```"""

                status, _headers, result = self.request(
                    "POST",
                    f"/api/document-versions/{version_id}/{mode}",
                    payload=payload,
                    user_id="editor-user",
                )
                self.assertEqual(status, 201, result)
                self.assertEqual(result["data"]["status"], "review_ready")
                self.assertTrue(result["data"]["reviewId"])
                self.assertEqual(result["data"]["sourceRecognitionJobId"], "")

        with audit_api.connect() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM project_records").fetchone()[0],
                before_projects,
            )

    def test_failed_job_can_enter_manual_review_and_external_parser_errors_are_explicit(self):
        created = self.create_document(project_id=None)
        self.add_page(created)
        job = self.create_job(created, status="failed")

        status, _headers, manual = self.request(
            "POST",
            f"/api/document-recognition-jobs/{job['id']}/manual-review",
            payload={
                "idempotencyKey": f"manual:{uuid.uuid4().hex}",
                "fallbackReason": "ocr_failed",
                "values": {},
            },
            user_id="editor-user",
        )
        self.assertEqual(status, 201, manual)
        self.assertEqual(manual["data"]["sourceRecognitionJobId"], job["id"])

        status, _headers, invalid = self.request(
            "POST",
            f"/api/document-recognition-jobs/{job['id']}/external-import",
            payload={
                "idempotencyKey": f"external:{uuid.uuid4().hex}",
                "fallbackReason": "external_ai",
                "markdown": "```json\n{broken}\n```",
            },
            user_id="editor-user",
        )
        self.assertEqual(status, 422)
        self.assertEqual(invalid["code"], "external_json_invalid")

    def test_page_image_supports_206_and_416_ranges(self):
        created = self.create_document()
        self.add_page(created, b"0123456789")
        path = f"/api/document-versions/{created['version']['id']}/pages/1/image"

        status, headers, body = self.request(
            "GET",
            path,
            headers={"Range": "bytes=2-5"},
            user_id="viewer-user",
        )
        self.assertEqual(status, 206)
        self.assertEqual(body, b"2345")
        self.assertEqual(headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(headers["Accept-Ranges"], "bytes")

        status, headers, _body = self.request(
            "GET",
            path,
            headers={"Range": "bytes=99-100"},
            user_id="viewer-user",
        )
        self.assertEqual(status, 416)
        self.assertEqual(headers["Content-Range"], "bytes */10")

    def test_review_detail_groups_fields_and_hides_storage_and_provider_data(self):
        _created, _page, _job, review = self.create_review(CONTRACT_FIELDS)

        status, _headers, payload = self.request(
            "GET",
            f"/api/document-reviews/{review['id']}",
            user_id="editor-user",
        )

        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertIn("document", data)
        self.assertIn("projectCandidates", data)
        self.assertIn("pages", data)
        self.assertIn("sections", data)
        self.assertIn("blockers", data)
        self.assertIn("warnings", data)
        self.assertIn("allowedCommands", data)
        self.assertTrue(any(section["key"] == "contract" for section in data["sections"]))
        self.assert_no_internal_fields(payload)

    def test_decision_conflict_is_409_and_validation_is_422(self):
        _created, _page, _job, review = self.create_review({"project.name": "测试工程"})
        field = review["fields"][0]
        path = f"/api/document-reviews/{review['id']}/decisions"
        valid = {
            "expectedReviewVersion": 0,
            "decisions": [{
                "fieldId": field["id"],
                "decision": "accepted",
                "confirmedValue": field["aiValue"],
            }],
        }

        status, _headers, saved = self.request(
            "POST", path, payload=valid, user_id="editor-user"
        )
        self.assertEqual(status, 200)
        self.assertEqual(saved["data"]["reviewVersion"], 1)

        status, _headers, conflict = self.request(
            "POST", path, payload=valid, user_id="editor-user"
        )
        self.assertEqual(status, 409)
        self.assertEqual(conflict["currentReviewVersion"], 1)

        status, _headers, invalid = self.request(
            "POST",
            path,
            payload={
                "expectedReviewVersion": 1,
                "decisions": [{
                    "fieldId": field["id"],
                    "decision": "modified",
                    "confirmedValue": "改后的项目名",
                }],
            },
            user_id="editor-user",
        )
        self.assertEqual(status, 422)
        self.assertEqual(invalid["code"], "modified_reason_required")

    def test_confirmation_blockers_return_422(self):
        _created, _page, _job, review = self.create_review({"project.name": "缺字段合同"})

        status, _headers, payload = self.request(
            "POST",
            f"/api/document-reviews/{review['id']}/confirm",
            payload={
                "expectedReviewVersion": 0,
                "idempotencyKey": f"confirm:{uuid.uuid4().hex}",
                "formTemplateVersion": "contract-form.v1",
            },
            user_id="admin-user",
        )

        self.assertEqual(status, 422)
        self.assertTrue(payload["blockers"])

    def test_confirmation_is_201_then_idempotent_200(self):
        _created, _page, _job, review = self.create_review(CONTRACT_FIELDS)
        review_version = 0
        saved = None
        for field in review["fields"]:
            status, _headers, saved = self.request(
                "POST",
                f"/api/document-reviews/{review['id']}/decisions",
                payload={
                    "expectedReviewVersion": review_version,
                    "decisions": [{
                        "fieldId": field["id"],
                        "decision": "accepted",
                        "confirmedValue": field["aiValue"],
                    }],
                },
                user_id="editor-user",
            )
            self.assertEqual(status, 200, saved)
            review_version = saved["data"]["reviewVersion"]
        confirm_payload = {
            "expectedReviewVersion": review_version,
            "idempotencyKey": f"confirm:{uuid.uuid4().hex}",
            "formTemplateVersion": "contract-form.v1",
        }

        status, _headers, first = self.request(
            "POST",
            f"/api/document-reviews/{review['id']}/confirm",
            payload=confirm_payload,
            user_id="editor-user",
        )
        self.project_scopes["editor-user"].add(first["data"]["projectId"])
        replay_status, _headers, replay = self.request(
            "POST",
            f"/api/document-reviews/{review['id']}/confirm",
            payload=confirm_payload,
            user_id="editor-user",
        )

        self.assertEqual(status, 201)
        self.assertEqual(replay_status, 200)
        self.assertFalse(first["data"]["replayed"])
        self.assertTrue(replay["data"]["replayed"])
        self.assertEqual(first["data"]["snapshotId"], replay["data"]["snapshotId"])
        self.assert_no_internal_fields(first)
        self.assert_no_internal_fields(replay)


if __name__ == "__main__":
    unittest.main()
