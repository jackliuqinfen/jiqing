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
            "project-records/project-2/two.pdf": b"two",
            "audit-projects/audit-1/audit.pdf": b"audit",
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
            conn.execute(
                """
                INSERT INTO audit_projects
                (id, project_id, project_code, project_name, created_at, updated_at)
                VALUES ('audit-1', 'project-1', 'AUD-001', '学校维修审计', ?, ?)
                """,
                (now, now),
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
                ],
            )
            conn.execute(
                """
                INSERT INTO audit_project_attachments
                (id, project_id, file_name, file_url, original_name, stored_name,
                 file_ext, mime_type, file_size, relative_path, uploaded_at, created_at)
                VALUES ('attachment-1', 'audit-1', 'audit.pdf',
                        'audit-projects/audit-1/audit.pdf', 'audit.pdf', 'audit.pdf',
                        '.pdf', 'application/pdf', 5,
                        'audit-projects/audit-1/audit.pdf',
                        '2026-07-27T09:00:00Z', '2026-07-27T09:00:00Z')
                """
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

    def enable_policy(self, **overrides):
        policy = {
            "enabled": True,
            "allowedRoles": ["editor", "admin"],
            "allowedUserIds": [],
            "projectSelectionMode": "user_select",
            "allowedProjectRefs": [],
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

    def test_sync_routes_require_authentication(self):
        status, _headers, payload = self.request(
            "GET",
            "/api/desktop/sync/projects",
        )
        self.assertEqual(status, 401)
        self.assertFalse(payload["success"])

    def test_disabled_policy_returns_403(self):
        status, _headers, payload = self.request(
            "GET",
            "/api/desktop/sync/projects",
            user_id="editor-user",
        )
        self.assertEqual(status, 403)
        self.assertEqual(payload["code"], "desktop_sync_disabled")

    def test_manifest_intersects_admin_assigned_projects(self):
        self.enable_policy(
            allowedRoles=["editor"],
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

        self.assertEqual(status, 200)
        self.assertEqual(
            {item["projectRef"] for item in payload["data"]["items"]},
            {"project:project-1"},
        )

    def test_next_cursor_does_not_duplicate_rows(self):
        self.enable_policy()
        first = self.manifest(limit=1)
        second = self.manifest(limit=1, cursor=first["nextCursor"])

        self.assertNotEqual(
            first["items"][0]["sourceId"],
            second["items"][0]["sourceId"],
        )

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

    def test_existing_project_scope_filters_roots_manifest_and_downloads(self):
        self.enable_policy()
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
        download_status, _headers, download_payload = self.request(
            "GET",
            "/api/project-files/file-2/download",
            user_id="limited-user",
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            {item["projectRef"] for item in roots_payload["data"]},
            {"project:project-1"},
        )
        self.assertEqual(manifest_status, 200)
        self.assertEqual(
            {item["projectRef"] for item in manifest_payload["data"]["items"]},
            {"project:project-1"},
        )
        self.assertEqual(download_status, 403)
        self.assertFalse(download_payload["success"])

    def test_manifest_reads_do_not_write_operation_logs(self):
        self.enable_policy()
        with audit_api.connect() as conn:
            before = conn.execute(
                "SELECT COUNT(*) AS count FROM system_operation_logs"
            ).fetchone()["count"]

        self.manifest()

        with audit_api.connect() as conn:
            after = conn.execute(
                "SELECT COUNT(*) AS count FROM system_operation_logs"
            ).fetchone()["count"]
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
