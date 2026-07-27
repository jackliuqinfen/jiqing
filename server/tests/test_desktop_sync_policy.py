import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import audit_api
from server.desktop_sync_policy import (
    DEFAULT_DESKTOP_SYNC_POLICY,
    effective_desktop_sync_policy,
    normalize_desktop_sync_policy,
)


class DesktopSyncPolicyTest(unittest.TestCase):
    def test_default_policy_is_disabled(self):
        policy = normalize_desktop_sync_policy({})
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["allowedRoles"], ["admin"])
        self.assertEqual(policy["projectSelectionMode"], "user_select")
        self.assertEqual(policy["pollIntervalSeconds"], 300)
        self.assertEqual(policy["maxFileSizeBytes"], 100 * 1024 * 1024)
        self.assertEqual(policy["maxLocalStorageBytes"], 10 * 1024 * 1024 * 1024)

    def test_normalizer_clamps_and_filters_untrusted_values(self):
        policy = normalize_desktop_sync_policy({
            "enabled": True,
            "allowedRoles": ["admin", "root", "viewer"],
            "allowedUserIds": [" user-1 ", "", 5],
            "allowedExtensions": ["PDF", ".docx", "../exe"],
            "pollIntervalSeconds": 1,
            "maxFileSizeMb": 9000,
            "maxLocalStorageGb": -1,
        })
        self.assertEqual(policy["allowedRoles"], ["admin", "viewer"])
        self.assertEqual(policy["allowedUserIds"], ["user-1"])
        self.assertEqual(policy["allowedExtensions"], [".pdf", ".docx"])
        self.assertEqual(policy["pollIntervalSeconds"], 60)
        self.assertEqual(policy["maxFileSizeBytes"], 500 * 1024 * 1024)
        self.assertEqual(policy["maxLocalStorageBytes"], 1 * 1024 * 1024 * 1024)

    def test_effective_policy_requires_role_or_user_allowance(self):
        stored = {**DEFAULT_DESKTOP_SYNC_POLICY, "enabled": True}
        viewer = effective_desktop_sync_policy(stored, {"id": "u1", "role": "viewer"})
        admin = effective_desktop_sync_policy(stored, {"id": "u2", "role": "admin"})
        self.assertFalse(viewer["enabledForCurrentUser"])
        self.assertTrue(admin["enabledForCurrentUser"])

    def test_normalizer_rejects_untrusted_boolean_and_numeric_values(self):
        policy = normalize_desktop_sync_policy({
            "enabled": "false",
            "enabledByDefault": "true",
            "allowFolderSelection": "false",
            "removeLocalFilesOnRevocation": 1,
            "maxFileSizeMb": "not-a-number",
            "maxLocalStorageGb": {},
            "pollIntervalSeconds": [],
            "policyVersion": "unknown",
        })
        self.assertFalse(policy["enabled"])
        self.assertFalse(policy["enabledByDefault"])
        self.assertTrue(policy["allowFolderSelection"])
        self.assertFalse(policy["removeLocalFilesOnRevocation"])
        self.assertEqual(policy["maxFileSizeBytes"], 100 * 1024 * 1024)
        self.assertEqual(policy["maxLocalStorageBytes"], 10 * 1024 * 1024 * 1024)
        self.assertEqual(policy["pollIntervalSeconds"], 300)
        self.assertEqual(policy["policyVersion"], 1)

    def test_normalizer_preserves_normalized_byte_values(self):
        normalized = normalize_desktop_sync_policy({
            "enabled": True,
            "maxFileSizeMb": 2,
            "maxLocalStorageGb": 3,
        })
        renormalized = normalize_desktop_sync_policy(normalized)
        effective = effective_desktop_sync_policy(normalized, {"id": "admin", "role": "admin"})
        self.assertEqual(renormalized["maxFileSizeBytes"], 2 * 1024 * 1024)
        self.assertEqual(renormalized["maxLocalStorageBytes"], 3 * 1024 * 1024 * 1024)
        self.assertEqual(effective["maxFileSizeBytes"], 2 * 1024 * 1024)
        self.assertEqual(effective["maxLocalStorageBytes"], 3 * 1024 * 1024 * 1024)


class DesktopSyncPolicyApiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tempdir.name)
        cls.original_db_path = os.environ.get("AUDIT_DB_PATH")
        os.environ["AUDIT_DB_PATH"] = str(cls.root / "audit.sqlite3")
        audit_api.bootstrap()
        cls.server = audit_api.ThreadingHTTPServer(("127.0.0.1", 0), audit_api.Handler)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls._create_user("admin-user", "desktop-admin", "admin")
        with audit_api.connect() as conn:
            row = conn.execute(
                "SELECT setting_value FROM system_settings WHERE setting_key = 'desktop_sync_policy'"
            ).fetchone()
        cls.initial_policy = json.loads(row["setting_value"])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2)
        if cls.original_db_path is None:
            os.environ.pop("AUDIT_DB_PATH", None)
        else:
            os.environ["AUDIT_DB_PATH"] = cls.original_db_path
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

    def token(self, user_id):
        return audit_api.sign_token({"sub": user_id, "exp": int(time.time()) + 300})

    def request(self, method, path, payload=None, user_id=None):
        headers = {}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if user_id:
            headers["Authorization"] = f"Bearer {self.token(user_id)}"
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, dict(response.headers), json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            with error:
                return error.code, dict(error.headers), json.loads(error.read().decode("utf-8"))

    def test_bootstrap_is_public_but_policy_requires_authentication(self):
        status, _headers, bootstrap = self.request("GET", "/api/desktop/bootstrap")
        self.assertEqual(status, 200)
        self.assertEqual(bootstrap["data"]["minimumDesktopVersion"], "1.0.0")

        status, _headers, payload = self.request("GET", "/api/desktop/policy")
        self.assertEqual(status, 401)
        self.assertFalse(payload["success"])

    def test_policy_setting_uses_display_units_and_policy_endpoint_uses_bytes(self):
        with audit_api.connect() as conn:
            row = conn.execute(
                "SELECT setting_value FROM system_settings WHERE setting_key = 'desktop_sync_policy'"
            ).fetchone()
        previous_version = json.loads(row["setting_value"])["policyVersion"]

        status, _headers, payload = self.request(
            "PUT",
            "/api/system/settings/desktop_sync_policy",
            {"value": {"enabled": True, "maxFileSizeMb": 2, "maxLocalStorageGb": 3}},
            "admin-user",
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])

        with audit_api.connect() as conn:
            row = conn.execute(
                "SELECT setting_value FROM system_settings WHERE setting_key = 'desktop_sync_policy'"
            ).fetchone()
        stored = json.loads(row["setting_value"])
        self.assertEqual(stored["maxFileSizeMb"], 2)
        self.assertEqual(stored["maxLocalStorageGb"], 3)
        self.assertEqual(stored["policyVersion"], previous_version + 1)
        self.assertNotIn("maxFileSizeBytes", stored)
        self.assertNotIn("maxLocalStorageBytes", stored)

        status, _headers, policy = self.request("GET", "/api/desktop/policy", user_id="admin-user")
        self.assertEqual(status, 200)
        self.assertEqual(policy["data"]["maxFileSizeBytes"], 2 * 1024 * 1024)
        self.assertEqual(policy["data"]["maxLocalStorageBytes"], 3 * 1024 * 1024 * 1024)
        self.assertNotIn("maxFileSizeMb", policy["data"])
        self.assertNotIn("maxLocalStorageGb", policy["data"])

    def test_initial_policy_includes_enabled_by_default(self):
        self.assertIn("enabledByDefault", self.initial_policy)
        self.assertFalse(self.initial_policy["enabledByDefault"])

    def test_invalid_policy_values_are_conservatively_normalized(self):
        status, _headers, payload = self.request(
            "PUT",
            "/api/system/settings/desktop_sync_policy",
            {"value": {
                "enabled": "false",
                "maxFileSizeMb": "not-a-number",
                "maxLocalStorageGb": {},
                "pollIntervalSeconds": [],
            }},
            "admin-user",
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])

        status, _headers, policy = self.request("GET", "/api/desktop/policy", user_id="admin-user")
        self.assertEqual(status, 200)
        self.assertFalse(policy["data"]["enabled"])
        self.assertEqual(policy["data"]["maxFileSizeBytes"], 100 * 1024 * 1024)
        self.assertEqual(policy["data"]["maxLocalStorageBytes"], 10 * 1024 * 1024 * 1024)
        self.assertEqual(policy["data"]["pollIntervalSeconds"], 300)

    def test_concurrent_policy_updates_increment_version_without_loss(self):
        barrier = threading.Barrier(2)
        errors = []

        with audit_api.connect() as conn:
            conn.execute(
                "UPDATE system_settings SET setting_value = ? WHERE setting_key = 'desktop_sync_policy'",
                (json.dumps({
                    "enabled": False,
                    "enabledByDefault": False,
                    "allowedRoles": ["admin"],
                    "allowedUserIds": [],
                    "projectSelectionMode": "user_select",
                    "allowedProjectRefs": [],
                    "allowedCategoryKeys": [],
                    "allowedExtensions": [".pdf"],
                    "maxFileSizeMb": 100,
                    "maxLocalStorageGb": 10,
                    "pollIntervalSeconds": 300,
                    "allowFolderSelection": True,
                    "removeLocalFilesOnRevocation": False,
                    "policyVersion": 1,
                }),),
            )

        class CoordinatedConnection:
            def __init__(self, conn):
                self.conn = conn

            def execute(self, statement, parameters=()):
                result = self.conn.execute(statement, parameters)
                if (
                    statement.startswith("SELECT setting_value FROM system_settings")
                    and "desktop_sync_policy" in statement
                ):
                    try:
                        barrier.wait(timeout=1)
                    except threading.BrokenBarrierError:
                        pass
                return result

            def commit(self):
                self.conn.commit()

        def update(max_file_size_mb):
            try:
                with audit_api.connect() as conn:
                    handler = object.__new__(audit_api.Handler)
                    handler.require_role = lambda _conn, _roles: {"username": "desktop-admin"}
                    handler.write_operation_log = lambda *_args: None
                    handler.respond = lambda *_args: None
                    audit_api.Handler.set_system_setting(
                        handler,
                        CoordinatedConnection(conn),
                        "desktop_sync_policy",
                        {"value": {"maxFileSizeMb": max_file_size_mb}},
                    )
            except Exception as exc:
                errors.append(exc)

        first = threading.Thread(target=update, args=(2,))
        second = threading.Thread(target=update, args=(3,))
        first.start()
        second.start()
        first.join(timeout=5)
        second.join(timeout=5)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])

        with audit_api.connect() as conn:
            row = conn.execute(
                "SELECT setting_value FROM system_settings WHERE setting_key = 'desktop_sync_policy'"
            ).fetchone()
        self.assertEqual(json.loads(row["setting_value"])["policyVersion"], 3)


if __name__ == "__main__":
    unittest.main()
