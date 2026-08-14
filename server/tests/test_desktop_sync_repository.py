import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.desktop_sync_repository import (
    InvalidSyncCursor,
    list_sync_manifest,
    list_sync_project_roots,
)


class DesktopSyncRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE project_records (
              id TEXT PRIMARY KEY,
              project_code TEXT NOT NULL,
              project_name TEXT NOT NULL,
              is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE project_files (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              category_key TEXT NOT NULL,
              display_name TEXT NOT NULL,
              original_name TEXT NOT NULL,
              file_ext TEXT DEFAULT '',
              mime_type TEXT DEFAULT '',
              file_size INTEGER DEFAULT 0,
              relative_path TEXT NOT NULL,
              version_no INTEGER DEFAULT 1,
              is_current INTEGER DEFAULT 1,
              uploaded_at TEXT NOT NULL,
              is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE project_document_categories (
              category_key TEXT PRIMARY KEY,
              category_name TEXT NOT NULL
            );
            CREATE TABLE audit_projects (
              id TEXT PRIMARY KEY,
              project_id TEXT DEFAULT '',
              project_code TEXT DEFAULT '',
              project_name TEXT NOT NULL,
              status TEXT DEFAULT 'active'
            );
            CREATE TABLE audit_project_attachments (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              file_name TEXT NOT NULL,
              original_name TEXT DEFAULT '',
              file_ext TEXT DEFAULT '',
              mime_type TEXT DEFAULT '',
              file_size INTEGER DEFAULT 0,
              relative_path TEXT DEFAULT '',
              uploaded_at TEXT NOT NULL,
              created_at TEXT DEFAULT '',
              is_deleted INTEGER DEFAULT 0
            );
            CREATE TABLE desktop_sync_hash_cache (
              source_type TEXT NOT NULL,
              source_id TEXT NOT NULL,
              revision_key TEXT NOT NULL,
              sha256 TEXT NOT NULL,
              file_size INTEGER NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY (source_type, source_id, revision_key)
            );
            """
        )
        self.conn.executemany(
            """
            INSERT INTO project_records
            (id, project_code, project_name, is_deleted)
            VALUES (?, ?, ?, 0)
            """,
            [
                ("project-1", "PRJ-001", "区直学校维修"),
                ("project-2", "PRJ-002", "办公楼改造"),
            ],
        )
        self.conn.execute(
            """
            INSERT INTO project_document_categories
            (category_key, category_name)
            VALUES ('contract', '合同文件')
            """
        )
        self.conn.executemany(
            """
            INSERT INTO audit_projects
            (id, project_id, project_code, project_name, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            [
                ("audit-1", "project-1", "AUD-001", "学校维修审计"),
                ("audit-2", "", "AUD-002", "独立审计项目"),
            ],
        )
        self._write("project-1/contract.pdf", b"project-file")
        self._write("audit-1/report.pdf", b"audit-file")
        self.conn.execute(
            """
            INSERT INTO project_files
            (id, project_id, category_key, display_name, original_name, file_ext,
             mime_type, file_size, relative_path, version_no, is_current,
             uploaded_at, is_deleted)
            VALUES
            ('file-1', 'project-1', 'contract', '施工合同', 'contract.pdf', '.pdf',
             'application/pdf', 12, 'project-1/contract.pdf', 1, 1,
             '2026-07-27T08:00:00Z', 0)
            """
        )
        self.conn.executemany(
            """
            INSERT INTO audit_project_attachments
            (id, project_id, file_name, original_name, file_ext, mime_type,
             file_size, relative_path, uploaded_at, created_at, is_deleted)
            VALUES (?, ?, ?, ?, '.pdf', 'application/pdf', ?, ?, ?, ?, 0)
            """,
            [
                (
                    "attachment-1",
                    "audit-1",
                    "report.pdf",
                    "report.pdf",
                    10,
                    "audit-1/report.pdf",
                    "2026-07-27T09:00:00Z",
                    "2026-07-27T09:00:00Z",
                ),
                (
                    "attachment-2",
                    "audit-2",
                    "missing.pdf",
                    "missing.pdf",
                    99,
                    "audit-2/missing.pdf",
                    "2026-07-27T10:00:00Z",
                    "2026-07-27T10:00:00Z",
                ),
            ],
        )
        self.policy = {
            "projectSelectionMode": "user_select",
            "allowedProjectRefs": [],
            "allowedCategoryKeys": [],
            "allowedExtensions": [".pdf"],
            "maxFileSizeBytes": 1024 * 1024,
            "policyVersion": 7,
        }

    def tearDown(self):
        self.conn.close()
        self.tempdir.cleanup()

    def _write(self, relative_path, content):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def path_resolver(self, relative_path):
        return self.root / relative_path

    def manifest(self, refs, cursor="", limit=200):
        return list_sync_manifest(
            self.conn,
            self.policy,
            refs,
            cursor=cursor,
            limit=limit,
            path_resolver=self.path_resolver,
        )

    def test_linked_audit_attachment_merges_into_project_root(self):
        roots = list_sync_project_roots(self.conn, self.policy)
        project = next(
            item for item in roots if item["projectRef"] == "project:project-1"
        )
        self.assertEqual(project["fileCount"], 2)
        self.assertEqual(project["projectName"], "区直学校维修")
        self.assertEqual(project["auditProjectId"], "audit-1")
        self.assertEqual(project["totalFileSizeBytes"], 22)

    def test_unlinked_audit_project_keeps_an_independent_root(self):
        roots = list_sync_project_roots(self.conn, self.policy)
        item = next(item for item in roots if item["projectRef"] == "audit:audit-2")
        self.assertIsNone(item["canonicalProjectId"])
        self.assertEqual(item["auditProjectId"], "audit-2")
        self.assertEqual(item["fileCount"], 1)

    def test_manifest_has_stable_source_revision_and_hash(self):
        result = self.manifest(["project:project-1"])
        entries = result["items"]
        self.assertEqual(
            {item["sourceType"] for item in entries},
            {"project_file", "audit_attachment"},
        )
        self.assertTrue(all(len(item["sha256"]) == 64 for item in entries))
        self.assertTrue(
            all(item["downloadPath"].startswith("/api/") for item in entries)
        )
        self.assertTrue(all(item["sourceRevision"] for item in entries))
        self.assertEqual(result["policyVersion"], 7)
        project_file = next(
            item for item in entries if item["sourceType"] == "project_file"
        )
        audit_attachment = next(
            item for item in entries if item["sourceType"] == "audit_attachment"
        )
        self.assertEqual(project_file["categoryName"], "合同文件")
        self.assertEqual(project_file["versionNo"], 1)
        self.assertEqual(audit_attachment["categoryName"], "审计附件")
        self.assertEqual(audit_attachment["versionNo"], 1)
        self.assertTrue(
            all(
                item["downloadPath"].startswith("/api/desktop/sync/files/")
                for item in entries
            )
        )

    def test_hash_cache_reuses_an_immutable_source_revision(self):
        first = self.manifest(["project:project-1"])
        first_item = next(
            item for item in first["items"] if item["sourceId"] == "file-1"
        )
        self._write("project-1/contract.pdf", b"changed-data")

        second = self.manifest(["project:project-1"])
        second_item = next(
            item for item in second["items"] if item["sourceId"] == "file-1"
        )
        cache_rows = self.conn.execute(
            "SELECT source_type, source_id, revision_key FROM desktop_sync_hash_cache"
        ).fetchall()

        self.assertEqual(first_item["sha256"], second_item["sha256"])
        self.assertEqual(first_item["sha256"], hashlib.sha256(b"project-file").hexdigest())
        self.assertEqual(len(cache_rows), 2)

    def test_hash_cache_invalidates_when_source_revision_changes(self):
        first = self.manifest(["project:project-1"])
        first_item = next(
            item for item in first["items"] if item["sourceId"] == "file-1"
        )
        self._write("project-1/contract.pdf", b"revised-file")
        self.conn.execute(
            """
            UPDATE project_files
            SET version_no = 2, file_size = 12
            WHERE id = 'file-1'
            """
        )

        second = self.manifest(["project:project-1"])
        second_item = next(
            item for item in second["items"] if item["sourceId"] == "file-1"
        )
        cache_rows = self.conn.execute(
            """
            SELECT revision_key, sha256
            FROM desktop_sync_hash_cache
            WHERE source_type = 'project_file' AND source_id = 'file-1'
            ORDER BY revision_key
            """
        ).fetchall()

        self.assertNotEqual(first_item["sourceRevision"], second_item["sourceRevision"])
        self.assertNotEqual(first_item["sha256"], second_item["sha256"])
        self.assertEqual(
            second_item["sha256"],
            hashlib.sha256(b"revised-file").hexdigest(),
        )
        self.assertEqual(len(cache_rows), 2)

    def test_missing_file_remains_in_root_and_manifest_without_download(self):
        roots = list_sync_project_roots(self.conn, self.policy)
        root = next(item for item in roots if item["projectRef"] == "audit:audit-2")
        result = self.manifest(["audit:audit-2"])

        self.assertEqual(root["fileCount"], 1)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["availability"], "missing")
        self.assertEqual(result["items"][0]["sha256"], "")
        self.assertIsNone(result["items"][0]["downloadPath"])

    def test_invalid_cursor_is_rejected(self):
        with self.assertRaises(InvalidSyncCursor):
            self.manifest(["project:project-1"], cursor="not-a-cursor")

    def test_next_cursor_does_not_duplicate_rows(self):
        first = self.manifest(["project:project-1"], limit=1)
        second = self.manifest(
            ["project:project-1"],
            cursor=first["nextCursor"],
            limit=1,
        )

        self.assertEqual(len(first["items"]), 1)
        self.assertEqual(len(second["items"]), 1)
        self.assertNotEqual(
            first["items"][0]["sourceId"],
            second["items"][0]["sourceId"],
        )

    def test_snapshot_defers_same_second_smaller_id_without_skip_or_duplicate(self):
        first = self.manifest(["project:project-1"], limit=1)
        self._write("project-1/late.pdf", b"late")
        self.conn.execute(
            """
            INSERT INTO project_files
            (id, project_id, category_key, display_name, original_name, file_ext,
             mime_type, file_size, relative_path, version_no, is_current,
             uploaded_at, is_deleted)
            VALUES
            ('aaa-late', 'project-1', 'contract', '后插资料', 'late.pdf', '.pdf',
             'application/pdf', 4, 'project-1/late.pdf', 1, 1,
             '2026-07-27T08:00:00Z', 0)
            """
        )

        final_page = self.manifest(
            ["project:project-1"],
            cursor=first["nextCursor"],
            limit=1,
        )
        resumed = self.manifest(
            ["project:project-1"],
            cursor=final_page["nextCursor"],
            limit=10,
        )

        self.assertTrue(first["hasMore"])
        self.assertFalse(final_page["hasMore"])
        self.assertTrue(final_page["nextCursor"])
        self.assertEqual(
            {first["items"][0]["sourceId"], final_page["items"][0]["sourceId"]},
            {"file-1", "attachment-1"},
        )
        self.assertEqual(
            [item["sourceId"] for item in resumed["items"]],
            ["aaa-late"],
        )
        self.assertFalse(resumed["hasMore"])
        self.assertTrue(resumed["nextCursor"])

    def test_only_page_returns_nonempty_resume_watermark(self):
        result = self.manifest(["audit:audit-2"], limit=200)
        resumed = self.manifest(
            ["audit:audit-2"],
            cursor=result["nextCursor"],
            limit=200,
        )

        self.assertFalse(result["hasMore"])
        self.assertTrue(result["nextCursor"])
        self.assertEqual(resumed["items"], [])
        self.assertFalse(resumed["hasMore"])
        self.assertTrue(resumed["nextCursor"])


if __name__ == "__main__":
    unittest.main()
