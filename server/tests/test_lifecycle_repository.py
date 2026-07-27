import sqlite3
import unittest

from server.lifecycle_repository import (
    LifecycleBlockedError,
    LifecycleConflictError,
    LifecycleIdempotencyConflictError,
    apply_pending_migrations,
    lifecycle_snapshot,
    transition_project,
)
from server.migrations import MigrationChecksumMismatchError


def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE project_records (
          id TEXT PRIMARY KEY,
          project_code TEXT UNIQUE NOT NULL,
          project_name TEXT NOT NULL,
          contract_date TEXT DEFAULT '',
          construction_unit TEXT DEFAULT '',
          owner_unit TEXT DEFAULT '',
          project_status TEXT DEFAULT 'awarded',
          contract_amount REAL DEFAULT 0,
          submitted_amount REAL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT DEFAULT '',
          is_deleted INTEGER DEFAULT 0
        );

        CREATE TABLE project_files (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          category_key TEXT NOT NULL,
          display_name TEXT NOT NULL,
          original_name TEXT NOT NULL,
          stored_name TEXT NOT NULL,
          relative_path TEXT NOT NULL,
          version_no INTEGER DEFAULT 1,
          is_current INTEGER DEFAULT 1,
          uploaded_at TEXT NOT NULL,
          deleted_at TEXT DEFAULT '',
          is_deleted INTEGER DEFAULT 0,
          FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    return conn


def insert_project(conn, project_id="project-1", **overrides):
    values = {
        "id": project_id,
        "project_code": f"PRJ-{project_id}",
        "project_name": "真实项目",
        "contract_date": "2026-07-11",
        "construction_unit": "施工单位",
        "owner_unit": "建设单位",
        "project_status": "awarded",
        "contract_amount": 100,
        "submitted_amount": 0,
        "created_at": "2026-07-11T00:00:00Z",
        "updated_at": "2026-07-11T00:00:00Z",
    }
    values.update(overrides)
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.execute(
        f"INSERT INTO project_records ({columns}) VALUES ({marks})",
        tuple(values.values()),
    )
    conn.commit()


def insert_contract_file(conn, project_id="project-1"):
    conn.execute(
        """
        INSERT INTO project_files
        (id, project_id, category_key, display_name, original_name, stored_name, relative_path, uploaded_at)
        VALUES (?, ?, 'contract', '合同.pdf', '合同.pdf', 'contract.pdf', 'files/contract.pdf', ?)
        """,
        (f"file-{project_id}", project_id, "2026-07-11T00:00:00Z"),
    )
    conn.commit()


class LifecycleRepositoryTests(unittest.TestCase):
    def test_migration_is_idempotent_and_records_success(self):
        conn = memory_conn()

        apply_pending_migrations(conn)
        apply_pending_migrations(conn)

        project_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(project_records)").fetchall()
        }
        event_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'project_lifecycle_events'"
        ).fetchone()
        migrations = conn.execute(
            "SELECT version, checksum, started_at, finished_at, success FROM schema_migrations"
        ).fetchall()

        self.assertIn("lifecycle_version", project_columns)
        self.assertIsNotNone(event_table)
        self.assertEqual(
            {row["version"]: row["success"] for row in migrations},
            {
                "2026071101_lifecycle_runtime": 1,
                "2026071301_document_evidence_phase1": 1,
                "2026071401_document_confirmation_guards": 1,
                "2026071501_contract_fallback": 1,
                "2026071502_contract_fallback_provenance": 1,
                "2026072701_desktop_sync_hash_cache": 1,
            },
        )
        lifecycle_migration = next(
            row
            for row in migrations
            if row["version"] == "2026071101_lifecycle_runtime"
        )
        self.assertTrue(lifecycle_migration["checksum"])
        self.assertTrue(lifecycle_migration["started_at"])
        self.assertTrue(lifecycle_migration["finished_at"])
        self.assertEqual(lifecycle_migration["success"], 1)

    def test_successful_migration_with_checksum_mismatch_raises_clear_error(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        conn.execute(
            "UPDATE schema_migrations SET checksum = 'outdated-checksum' WHERE version = ?",
            ("2026071101_lifecycle_runtime",),
        )
        conn.commit()

        with self.assertRaises(MigrationChecksumMismatchError) as raised:
            apply_pending_migrations(conn)

        migration = conn.execute(
            "SELECT checksum, success FROM schema_migrations WHERE version = ?",
            ("2026071101_lifecycle_runtime",),
        ).fetchone()
        self.assertIn("checksum mismatch", str(raised.exception).lower())
        self.assertEqual(migration["checksum"], "outdated-checksum")
        self.assertEqual(migration["success"], 1)

    def test_failed_migration_can_be_retried_after_root_cause_is_removed(self):
        conn = memory_conn()
        conn.execute("CREATE VIEW project_lifecycle_events AS SELECT 'blocked' AS id")
        conn.commit()

        with self.assertRaises(sqlite3.OperationalError):
            apply_pending_migrations(conn)

        failed_migration = conn.execute(
            "SELECT success FROM schema_migrations WHERE version = ?",
            ("2026071101_lifecycle_runtime",),
        ).fetchone()
        self.assertEqual(failed_migration["success"], 0)

        conn.execute("DROP VIEW project_lifecycle_events")
        conn.commit()
        apply_pending_migrations(conn)

        recovered_migration = conn.execute(
            "SELECT success FROM schema_migrations WHERE version = ?",
            ("2026071101_lifecycle_runtime",),
        ).fetchone()
        self.assertEqual(recovered_migration["success"], 1)

    def test_snapshot_returns_next_transition_blockers(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn, contract_date="", contract_amount=0, owner_unit="")

        snapshot = lifecycle_snapshot(conn, "project-1")

        self.assertEqual(snapshot["projectId"], "project-1")
        self.assertEqual(snapshot["currentStage"], "awarded")
        self.assertEqual(snapshot["currentStageLabel"], "已中标")
        self.assertEqual(snapshot["lifecycleVersion"], 0)
        self.assertEqual(snapshot["nextTransition"]["toStage"], "contract_signed")
        self.assertEqual(
            [blocker["code"] for blocker in snapshot["nextTransition"]["blockers"]],
            [
                "contract_date_required",
                "contract_amount_required",
                "owner_unit_required",
                "contract_file_required",
            ],
        )

    def test_successful_transition_updates_status_version_and_event_once(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn)
        insert_contract_file(conn)

        result = transition_project(
            conn,
            "project-1",
            "contract_signed",
            expected_version=0,
            idempotency_key="idem-1",
            reason="合同已确认",
            actor={"id": "u-1", "name": "实施人"},
        )

        row = conn.execute("SELECT * FROM project_records WHERE id = 'project-1'").fetchone()
        events = conn.execute("SELECT * FROM project_lifecycle_events").fetchall()

        self.assertEqual(row["project_status"], "contract_signed")
        self.assertEqual(row["lifecycle_version"], 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["from_stage"], "awarded")
        self.assertEqual(events[0]["to_stage"], "contract_signed")
        self.assertEqual(events[0]["idempotency_key"], "idem-1")
        self.assertEqual(events[0]["lifecycle_version"], 1)
        self.assertEqual(result["currentStage"], "contract_signed")
        self.assertEqual(result["lifecycleVersion"], 1)
        self.assertEqual(result["event"]["id"], events[0]["id"])

    def test_blocker_rolls_back_without_status_or_event(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn)

        with self.assertRaises(LifecycleBlockedError) as raised:
            transition_project(
                conn,
                "project-1",
                "contract_signed",
                expected_version=0,
                idempotency_key="idem-blocked",
                reason="缺少合同附件",
                actor={"id": "u-1", "name": "实施人"},
            )

        row = conn.execute("SELECT project_status, lifecycle_version FROM project_records WHERE id = 'project-1'").fetchone()
        event_count = conn.execute("SELECT COUNT(*) AS c FROM project_lifecycle_events").fetchone()["c"]

        self.assertEqual(row["project_status"], "awarded")
        self.assertEqual(row["lifecycle_version"], 0)
        self.assertIn("contract_file_required", [item["code"] for item in raised.exception.blockers])
        self.assertEqual(event_count, 0)

    def test_idempotent_replay_returns_existing_event_without_new_row(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn)
        insert_contract_file(conn)

        first = transition_project(
            conn,
            "project-1",
            "contract_signed",
            expected_version=0,
            idempotency_key="idem-replay",
            reason="第一次提交",
            actor={"id": "u-1", "name": "实施人"},
        )
        replay = transition_project(
            conn,
            "project-1",
            "contract_signed",
            expected_version=0,
            idempotency_key="idem-replay",
            reason="网络重试",
            actor={"id": "u-1", "name": "实施人"},
        )

        event_count = conn.execute("SELECT COUNT(*) AS c FROM project_lifecycle_events").fetchone()["c"]
        self.assertEqual(replay, first)
        self.assertEqual(event_count, 1)

    def test_idempotency_key_replay_with_different_target_stage_conflicts(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn)
        insert_contract_file(conn)
        transition_project(
            conn,
            "project-1",
            "contract_signed",
            expected_version=0,
            idempotency_key="idem-target-conflict",
            reason="首次提交",
            actor={},
        )

        with self.assertRaises(LifecycleIdempotencyConflictError) as raised:
            transition_project(
                conn,
                "project-1",
                "entry_in_site",
                expected_version=1,
                idempotency_key="idem-target-conflict",
                reason="错误重放",
                actor={},
            )

        event_count = conn.execute("SELECT COUNT(*) AS c FROM project_lifecycle_events").fetchone()["c"]
        self.assertEqual(raised.exception.existing_target_stage, "contract_signed")
        self.assertEqual(raised.exception.requested_target_stage, "entry_in_site")
        self.assertEqual(event_count, 1)

    def test_idempotency_key_is_scoped_to_project(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn, "project-1")
        insert_project(conn, "project-2")
        insert_contract_file(conn, "project-1")
        insert_contract_file(conn, "project-2")

        transition_project(conn, "project-1", "contract_signed", 0, "same-key", "", {})
        transition_project(conn, "project-2", "contract_signed", 0, "same-key", "", {})

        event_count = conn.execute("SELECT COUNT(*) AS c FROM project_lifecycle_events").fetchone()["c"]
        self.assertEqual(event_count, 2)

    def test_stale_expected_version_conflicts_and_does_not_write(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn, lifecycle_version=2)
        insert_contract_file(conn)

        with self.assertRaises(LifecycleConflictError) as raised:
            transition_project(
                conn,
                "project-1",
                "contract_signed",
                expected_version=1,
                idempotency_key="idem-stale",
                reason="旧版本",
                actor={},
            )

        row = conn.execute("SELECT project_status, lifecycle_version FROM project_records WHERE id = 'project-1'").fetchone()
        event_count = conn.execute("SELECT COUNT(*) AS c FROM project_lifecycle_events").fetchone()["c"]

        self.assertEqual(raised.exception.current_version, 2)
        self.assertEqual(row["project_status"], "awarded")
        self.assertEqual(row["lifecycle_version"], 2)
        self.assertEqual(event_count, 0)

    def test_event_insert_failure_rolls_back_status_update(self):
        conn = memory_conn()
        apply_pending_migrations(conn)
        insert_project(conn)
        insert_contract_file(conn)
        conn.execute(
            """
            CREATE TRIGGER fail_lifecycle_event_insert
            BEFORE INSERT ON project_lifecycle_events
            BEGIN
              SELECT RAISE(ABORT, 'event insert failed');
            END;
            """
        )
        conn.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            transition_project(
                conn,
                "project-1",
                "contract_signed",
                expected_version=0,
                idempotency_key="idem-fail",
                reason="触发插入失败",
                actor={},
            )

        row = conn.execute("SELECT project_status, lifecycle_version FROM project_records WHERE id = 'project-1'").fetchone()
        self.assertEqual(row["project_status"], "awarded")
        self.assertEqual(row["lifecycle_version"], 0)


if __name__ == "__main__":
    unittest.main()
