import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from server import audit_api


class DesktopSyncApiContractTest(unittest.TestCase):
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
            "editor-user": {"project-1", "project-2"},
            "limited-user": {"project-1"},
        }

        class ScopedHandler(audit_api.Handler):
            @staticmethod
            def document_project_scope_provider(_conn, actor):
                if actor["role"] == "admin":
                    return None
                return cls.project_scopes.get(actor["id"], set())

        cls.server = audit_api.ThreadingHTTPServer(("127.0.0.1", 0), ScopedHandler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever,
            daemon=True,
        )
        cls.server_thread.start()

        cls._create_user("admin-user", "desktop-admin", "admin")
        cls._create_user("editor-user", "desktop-editor", "editor")
        cls._create_user("limited-user", "desktop-limited", "editor")
        cls._create_fixtures()

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
    def _create_user(cls, user_id, username, role):
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
                    username,
                    audit_api.hash_password("test-password"),
                    role,
                    now,
                    now,
                ),
            )

    @classmethod
    def _create_fixtures(cls):
        upload_root = Path(os.environ["UPLOAD_ROOT"])
        files = {
            "project-records/project-1/one.pdf": b"one",
            "project-records/project-1/big.pdf": b"large-metadata-only",
            "project-records/project-2/two.pdf": b"two",
            "audit-projects/audit-1/audit.pdf": b"audit",
            "audit-projects/audit-2/audit.pdf": b"audit-two",
        }
        for relative_path, content in files.items():
            target = upload_root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        now = "2026-07-27T08:00:00Z"
        with audit_api.connect() as conn:
            conn.executemany(
                """
                INSERT INTO project_records
                (id, project_code, project_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("project-1", "PRJ-001", "学校维修", now, now),
                    ("project-2", "PRJ-002", "办公楼改造", now, now),
                ],
            )
            conn.executemany(
                """
                INSERT INTO audit_projects
                (id, project_id, project_code, project_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("audit-1", "project-1", "AUD-001", "学校维修审计", now, now),
                    ("audit-2", "project-2", "AUD-002", "办公楼改造审计", now, now),
                ],
            )
            conn.executemany(
                """
                INSERT INTO project_files
                (id, project_id, category_key, display_name, original_name,
                 stored_name, file_ext, mime_type, file_size, relative_path,
                 version_no, is_current, uploaded_at)
                VALUES (?, ?, 'contract', ?, ?, ?, '.pdf', 'application/pdf',
                        3, ?, 1, 1, ?)
                """,
                [
                    (
                        "file-1",
                        "project-1",
                        "项目一合同",
                        "one.pdf",
                        "one.pdf",
                        "project-records/project-1/one.pdf",
                        "2026-07-27T08:00:00Z",
                    ),
                    (
                        "file-2",
                        "project-2",
                        "项目二合同",
                        "two.pdf",
                        "two.pdf",
                        "project-records/project-2/two.pdf",
                        "2026-07-27T08:30:00Z",
                    ),
                    (
                        "file-big",
                        "project-1",
                        "大体积资料",
                        "big.pdf",
                        "big.pdf",
                        "project-records/project-1/big.pdf",
                        "2026-07-27T08:45:00Z",
                    ),
                ],
            )
            conn.execute(
                """
                UPDATE project_files
                SET file_size = 2097152
                WHERE id = 'file-big'
                """
            )
            conn.executemany(
                """
                INSERT INTO audit_project_attachments
                (id, project_id, file_name, file_url, original_name, stored_name,
                 file_ext, mime_type, file_size, relative_path, uploaded_at, created_at)
                VALUES (?, ?, 'audit.pdf', ?, 'audit.pdf', 'audit.pdf',
                        '.pdf', 'application/pdf', ?, ?, ?, ?)
                """,
                [
                    (
                        "attachment-1",
                        "audit-1",
                        "audit-projects/audit-1/audit.pdf",
                        5,
                        "audit-projects/audit-1/audit.pdf",
                        "2026-07-27T09:00:00Z",
                        "2026-07-27T09:00:00Z",
                    ),
                    (
                        "attachment-2",
                        "audit-2",
                        "audit-projects/audit-2/audit.pdf",
                        9,
                        "audit-projects/audit-2/audit.pdf",
                        "2026-07-27T09:30:00Z",
                        "2026-07-27T09:30:00Z",
                    ),
                ],
            )

    def setUp(self):
        self.enable_policy(enabled=False)

    def token(self, user_id):
        return audit_api.sign_token(
            {"sub": user_id, "exp": int(time.time()) + 300}
        )

    def request(self, method, path, user_id=None):
        headers = {}
        if user_id:
            headers["Authorization"] = f"Bearer {self.token(user_id)}"
        request = Request(
            f"{self.base_url}{path}",
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                return (
                    response.status,
                    dict(response.headers),
                    json.loads(response.read().decode("utf-8")),
                )
        except HTTPError as error:
            with error:
                return (
                    error.code,
                    dict(error.headers),
                    json.loads(error.read().decode("utf-8")),
                )

    def request_raw(self, method, path, user_id=None):
        headers = {}
        if user_id:
            headers["Authorization"] = f"Bearer {self.token(user_id)}"
        request = Request(
            f"{self.base_url}{path}",
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, dict(response.headers), response.read()
        except HTTPError as error:
            with error:
                return error.code, dict(error.headers), error.read()

    def enable_policy(self, **overrides):
        policy = {
            "enabled": True,
            "allowedRoles": ["admin"],
            "allowedUserIds": ["editor-user", "limited-user"],
            "projectSelectionMode": "admin_assigned",
            "allowedProjectRefs": [
                "project:project-1",
                "project:project-2",
            ],
            "allowedCategoryKeys": [],
            "allowedExtensions": [".pdf"],
            "maxFileSizeMb": 10,
            "maxLocalStorageGb": 1,
            "pollIntervalSeconds": 300,
            "allowFolderSelection": True,
            "removeLocalFilesOnRevocation": False,
            "policyVersion": 1,
            **overrides,
        }
        with audit_api.connect() as conn:
            conn.execute(
                """
                UPDATE system_settings
                SET setting_value = ?
                WHERE setting_key = 'desktop_sync_policy'
                """,
                (json.dumps(policy, ensure_ascii=False),),
            )

    def manifest(self, user_id="editor-user", limit=200, cursor=""):
        refs = quote("project:project-1", safe="")
        path = (
            f"/api/desktop/sync/manifest?projectRefs={refs}"
            f"&limit={limit}&cursor={quote(cursor, safe='')}"
        )
        status, _headers, payload = self.request("GET", path, user_id=user_id)
        self.assertEqual(status, 200)
        return payload["data"]

    def sync_download_path(self, source_type, source_id, revision):
        return (
            f"/api/desktop/sync/files/{source_type}/{source_id}/download"
            f"?revision={quote(revision, safe='')}"
        )

    def test_sync_routes_require_authentication(self):
        status, _headers, payload = self.request(
            "GET",
            "/api/desktop/sync/projects",
        )
        download_status, _headers, download_payload = self.request(
            "GET",
            self.sync_download_path(
                "project_file",
                "file-1",
                "file-1:1:3:2026-07-27T08:00:00Z",
            ),
        )
        self.assertEqual(status, 401)
        self.assertFalse(payload["success"])
        self.assertEqual(download_status, 401)
        self.assertFalse(download_payload["success"])

    def test_disabled_policy_returns_403(self):
        status, _headers, payload = self.request(
            "GET",
            "/api/desktop/sync/projects",
            user_id="editor-user",
        )
        download_status, _headers, download_payload = self.request(
            "GET",
            self.sync_download_path(
                "project_file",
                "file-1",
                "file-1:1:3:2026-07-27T08:00:00Z",
            ),
            user_id="editor-user",
        )
        self.assertEqual(status, 403)
        self.assertEqual(payload["code"], "desktop_sync_disabled")
        self.assertEqual(download_status, 403)
        self.assertEqual(
            download_payload["code"],
            "desktop_sync_disabled",
        )

    def test_manifest_rejects_any_project_removed_from_assignment(self):
        self.enable_policy(
            projectSelectionMode="admin_assigned",
            allowedProjectRefs=["project:project-1"],
        )
        requested = quote(
            "project:project-1,project:project-2",
            safe="",
        )
        status, _headers, payload = self.request(
            "GET",
            f"/api/desktop/sync/manifest?projectRefs={requested}",
            user_id="editor-user",
        )

        self.assertEqual(status, 403)
        self.assertEqual(payload["code"], "desktop_sync_scope_changed")
        self.assertEqual(payload["revokedProjectRefs"], ["project:project-2"])
        self.assertEqual(payload["policyVersion"], 1)

    def test_next_cursor_does_not_duplicate_rows(self):
        self.enable_policy()
        first = self.manifest(limit=1)
        second = self.manifest(limit=1, cursor=first["nextCursor"])

        self.assertNotEqual(
            first["items"][0]["sourceId"],
            second["items"][0]["sourceId"],
        )

    def test_manifest_exposes_complete_task_6_contract(self):
        self.enable_policy(policyVersion=9)
        status, _headers, roots_payload = self.request(
            "GET",
            "/api/desktop/sync/projects",
            user_id="editor-user",
        )
        result = self.manifest()
        project_file = next(
            item for item in result["items"] if item["sourceId"] == "file-1"
        )
        audit_attachment = next(
            item
            for item in result["items"]
            if item["sourceId"] == "attachment-1"
        )
        project_root = next(
            item
            for item in roots_payload["data"]
            if item["projectRef"] == "project:project-1"
        )

        self.assertEqual(status, 200)
        self.assertEqual(result["policyVersion"], 9)
        self.assertEqual(project_file["categoryName"], "合同文件")
        self.assertEqual(project_file["versionNo"], 1)
        self.assertEqual(audit_attachment["categoryName"], "审计附件")
        self.assertEqual(audit_attachment["versionNo"], 1)
        self.assertEqual(project_root["totalFileSizeBytes"], 2097160)
        self.assertTrue(result["nextCursor"])

    def test_invalid_cursor_returns_structured_400(self):
        self.enable_policy()
        refs = quote("project:project-1", safe="")
        status, _headers, payload = self.request(
            "GET",
            f"/api/desktop/sync/manifest?projectRefs={refs}&cursor=invalid",
            user_id="editor-user",
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "invalid_sync_cursor")

    def test_explicit_assignment_filters_sync_and_web_scope_still_applies(self):
        self.enable_policy(
            allowedUserIds=["limited-user"],
            allowedProjectRefs=["project:project-1"],
        )
        status, _headers, roots_payload = self.request(
            "GET",
            "/api/desktop/sync/projects",
            user_id="limited-user",
        )
        requested = quote(
            "project:project-1,project:project-2",
            safe="",
        )
        manifest_status, _headers, manifest_payload = self.request(
            "GET",
            f"/api/desktop/sync/manifest?projectRefs={requested}",
            user_id="limited-user",
        )
        download_status, _headers, download_body = self.request_raw(
            "GET",
            "/api/project-files/file-2/download",
            user_id="limited-user",
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            {item["projectRef"] for item in roots_payload["data"]},
            {"project:project-1"},
        )
        self.assertEqual(manifest_status, 403)
        self.assertEqual(
            manifest_payload["code"],
            "desktop_sync_scope_changed",
        )
        self.assertEqual(
            manifest_payload["revokedProjectRefs"],
            ["project:project-2"],
        )
        self.assertEqual(download_status, 403)
        self.assertFalse(json.loads(download_body.decode("utf-8"))["success"])

    def test_sync_download_rechecks_project_category_extension_and_size_policy(self):
        cases = [
            (
                "admin assigned project",
                "project_file",
                "file-2",
                "file-2:1:3:2026-07-27T08:30:00Z",
                "/api/project-files/file-2/download",
                {
                    "projectSelectionMode": "admin_assigned",
                    "allowedProjectRefs": ["project:project-1"],
                },
            ),
            (
                "category",
                "project_file",
                "file-1",
                "file-1:1:3:2026-07-27T08:00:00Z",
                "/api/project-files/file-1/download",
                {"allowedCategoryKeys": ["drawing"]},
            ),
            (
                "extension",
                "project_file",
                "file-1",
                "file-1:1:3:2026-07-27T08:00:00Z",
                "/api/project-files/file-1/download",
                {"allowedExtensions": [".docx"]},
            ),
            (
                "size",
                "project_file",
                "file-big",
                "file-big:1:2097152:2026-07-27T08:45:00Z",
                "/api/project-files/file-big/download",
                {"maxFileSizeMb": 1},
            ),
        ]
        for label, source_type, source_id, revision, web_path, policy in cases:
            with self.subTest(label=label):
                self.enable_policy(**policy)
                status, _headers, body = self.request_raw(
                    "GET",
                    self.sync_download_path(source_type, source_id, revision),
                    user_id="editor-user",
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    json.loads(body.decode("utf-8"))["code"],
                    "desktop_sync_source_forbidden",
                )
                web_status, _headers, _web_body = self.request_raw(
                    "GET",
                    web_path,
                    user_id="editor-user",
                )
                self.assertEqual(web_status, 200)

    def test_allowed_sync_download_rechecks_exact_source_revision(self):
        self.enable_policy()
        result = self.manifest()
        item = next(
            entry for entry in result["items"] if entry["sourceId"] == "file-1"
        )
        allowed_status, _headers, allowed_body = self.request_raw(
            "GET",
            item["downloadPath"],
            user_id="editor-user",
        )
        self.assertEqual(allowed_status, 200)
        self.assertEqual(allowed_body, b"one")

        try:
            with audit_api.connect() as conn:
                conn.execute(
                    "UPDATE project_files SET version_no = 2 WHERE id = 'file-1'"
                )
            stale_status, _headers, stale_body = self.request_raw(
                "GET",
                item["downloadPath"],
                user_id="editor-user",
            )
            self.assertEqual(stale_status, 409)
            self.assertEqual(
                json.loads(stale_body.decode("utf-8"))["code"],
                "desktop_sync_revision_changed",
            )
        finally:
            with audit_api.connect() as conn:
                conn.execute(
                    "UPDATE project_files SET version_no = 1 WHERE id = 'file-1'"
                )

    def test_out_of_scope_audit_attachment_sync_download_is_forbidden(self):
        self.enable_policy(
            allowedUserIds=["limited-user"],
            allowedProjectRefs=["project:project-1"],
        )
        revision = "attachment-2:9:2026-07-27T09:30:00Z"
        sync_status, _headers, sync_body = self.request_raw(
            "GET",
            self.sync_download_path(
                "audit_attachment",
                "attachment-2",
                revision,
            ),
            user_id="limited-user",
        )
        web_status, _headers, web_body = self.request_raw(
            "GET",
            "/api/audit/attachments/attachment-2/download",
            user_id="limited-user",
        )

        self.assertEqual(sync_status, 403)
        self.assertEqual(
            json.loads(sync_body.decode("utf-8"))["code"],
            "desktop_sync_source_forbidden",
        )
        self.assertEqual(web_status, 403)
        self.assertFalse(json.loads(web_body.decode("utf-8"))["success"])

    def test_sync_reads_do_not_write_business_or_audit_logs(self):
        self.enable_policy()
        with audit_api.connect() as conn:
            before = {
                table: conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table}"
                ).fetchone()["count"]
                for table in (
                    "system_operation_logs",
                    "project_operation_logs",
                    "audit_project_logs",
                )
            }

        self.request(
            "GET",
            "/api/desktop/sync/projects",
            user_id="editor-user",
        )
        result = self.manifest()
        item = next(
            entry for entry in result["items"] if entry["sourceId"] == "file-1"
        )
        download_status, _headers, _body = self.request_raw(
            "GET",
            item["downloadPath"],
            user_id="editor-user",
        )

        with audit_api.connect() as conn:
            after = {
                table: conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table}"
                ).fetchone()["count"]
                for table in before
            }
        self.assertEqual(download_status, 200)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
