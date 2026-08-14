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


class CurrentUserProfileApiTest(unittest.TestCase):
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
        cls._create_user("profile-user", "profile.user", "editor")
        cls._create_user("duplicate-user", "already.used", "viewer")

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
                    "测试用户",
                    audit_api.hash_password("current-password"),
                    role,
                    now,
                    now,
                ),
            )

    def token(self, user_id="profile-user"):
        return audit_api.sign_token({
            "sub": user_id,
            "exp": int(time.time()) + 300,
        })

    def request(self, method, path, body=None, user_id="profile-user"):
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Authorization": f"Bearer {self.token(user_id)}",
            "Content-Type": "application/json",
        }
        request = Request(
            f"{self.base_url}{path}",
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read().decode("utf-8"))

    def test_current_user_can_update_own_profile_without_changing_role(self):
        avatar = "data:image/png;base64,iVBORw0KGgo="
        status, payload = self.request("PUT", "/api/auth/profile", {
            "username": "profile.updated",
            "displayName": "刘建祥",
            "email": "user@example.com",
            "avatarUrl": avatar,
            "phone": "13800000000",
            "department": "工程管理部",
            "jobTitle": "项目经理",
            "bio": "负责项目全过程协同。",
            "role": "admin",
        })

        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["username"], "profile.updated")
        self.assertEqual(payload["data"]["displayName"], "刘建祥")
        self.assertEqual(payload["data"]["avatarUrl"], avatar)
        self.assertEqual(payload["data"]["department"], "工程管理部")
        self.assertEqual(payload["data"]["role"], "editor")

    def test_duplicate_username_is_rejected(self):
        status, payload = self.request("PUT", "/api/auth/profile", {
            "username": "already.used",
            "displayName": "测试用户",
            "email": "",
            "avatarUrl": "",
            "phone": "",
            "department": "",
            "jobTitle": "",
            "bio": "",
        })

        self.assertEqual(status, 409)
        self.assertFalse(payload["success"])

    def test_password_change_requires_current_password_and_updates_hash(self):
        rejected_status, rejected = self.request("PUT", "/api/auth/password", {
            "currentPassword": "wrong-password",
            "newPassword": "new-secure-password",
        })
        self.assertEqual(rejected_status, 400)
        self.assertFalse(rejected["success"])

        status, payload = self.request("PUT", "/api/auth/password", {
            "currentPassword": "current-password",
            "newPassword": "new-secure-password",
        })
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        with audit_api.connect() as conn:
            row = conn.execute(
                "SELECT password_hash FROM system_users WHERE id = 'profile-user'"
            ).fetchone()
        self.assertTrue(audit_api.verify_password("new-secure-password", row["password_hash"]))
        self.assertFalse(audit_api.verify_password("current-password", row["password_hash"]))


if __name__ == "__main__":
    unittest.main()
