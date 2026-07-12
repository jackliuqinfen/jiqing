"""SQLite schema migrations for the Shenjikanban server."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


LIFECYCLE_RUNTIME_MIGRATION = "2026071101_lifecycle_runtime"


class MigrationChecksumMismatchError(RuntimeError):
    """Raised when an applied migration no longer matches its definition."""

    def __init__(self, version, recorded_checksum, expected_checksum):
        super().__init__(
            f"Migration checksum mismatch for {version}: "
            f"recorded {recorded_checksum!r}, expected {expected_checksum!r}"
        )
        self.version = version
        self.recorded_checksum = recorded_checksum
        self.expected_checksum = expected_checksum


_LIFECYCLE_VERSION_ALTER_SQL = """
ALTER TABLE project_records ADD COLUMN lifecycle_version INTEGER NOT NULL DEFAULT 0
"""

_LIFECYCLE_EVENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS project_lifecycle_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  from_stage TEXT NOT NULL,
  to_stage TEXT NOT NULL,
  transition_type TEXT NOT NULL DEFAULT 'forward',
  reason TEXT DEFAULT '',
  idempotency_key TEXT NOT NULL,
  lifecycle_version INTEGER NOT NULL,
  actor_id TEXT DEFAULT '',
  actor_name TEXT DEFAULT '',
  payload_json TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES project_records(id) ON DELETE CASCADE,
  UNIQUE (project_id, idempotency_key)
)
"""

_LIFECYCLE_RUNTIME_STATEMENTS = (
    _LIFECYCLE_EVENT_TABLE_SQL,
    """
    CREATE INDEX IF NOT EXISTS idx_project_lifecycle_events_project
    ON project_lifecycle_events(project_id, created_at DESC)
    """,
)

_LIFECYCLE_RUNTIME_MIGRATION_DEFINITION = (
    _LIFECYCLE_VERSION_ALTER_SQL,
    *_LIFECYCLE_RUNTIME_STATEMENTS,
)

LIFECYCLE_RUNTIME_CHECKSUM = hashlib.sha256(
    "\n".join(
        statement.strip() for statement in _LIFECYCLE_RUNTIME_MIGRATION_DEFINITION
    ).encode("utf-8")
).hexdigest()


def apply_pending_migrations(conn):
    """Apply pending SQLite migrations once and record their success state."""
    _ensure_schema_migrations_table(conn)
    started_at = _now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT success, checksum FROM schema_migrations WHERE version = ?",
            (LIFECYCLE_RUNTIME_MIGRATION,),
        ).fetchone()
        if row and int(_value(row, "success", 0)) == 1:
            recorded_checksum = _value(row, "checksum", 1)
            if recorded_checksum != LIFECYCLE_RUNTIME_CHECKSUM:
                raise MigrationChecksumMismatchError(
                    LIFECYCLE_RUNTIME_MIGRATION,
                    recorded_checksum,
                    LIFECYCLE_RUNTIME_CHECKSUM,
                )
            conn.commit()
            return

        if row:
            conn.execute(
                """
                UPDATE schema_migrations
                SET checksum = ?, started_at = ?, finished_at = '', success = 0
                WHERE version = ?
                """,
                (LIFECYCLE_RUNTIME_CHECKSUM, started_at, LIFECYCLE_RUNTIME_MIGRATION),
            )
        else:
            conn.execute(
                """
                INSERT INTO schema_migrations
                (version, checksum, started_at, finished_at, success)
                VALUES (?, ?, ?, '', 0)
                """,
                (LIFECYCLE_RUNTIME_MIGRATION, LIFECYCLE_RUNTIME_CHECKSUM, started_at),
            )
        if _table_exists(conn, "project_records") and not _column_exists(
            conn,
            "project_records",
            "lifecycle_version",
        ):
            conn.execute(_LIFECYCLE_VERSION_ALTER_SQL)
        for statement in _LIFECYCLE_RUNTIME_STATEMENTS:
            conn.execute(statement)
        conn.execute(
            """
            UPDATE schema_migrations
            SET checksum = ?, finished_at = ?, success = 1
            WHERE version = ?
            """,
            (LIFECYCLE_RUNTIME_CHECKSUM, _now_iso(), LIFECYCLE_RUNTIME_MIGRATION),
        )
        conn.commit()
    except MigrationChecksumMismatchError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        _record_failed_migration(conn, started_at)
        raise


def _ensure_schema_migrations_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          checksum TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT DEFAULT '',
          success INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def _record_failed_migration(conn, started_at):
    try:
        cursor = conn.execute(
            """
            UPDATE schema_migrations
            SET checksum = ?, started_at = ?, finished_at = ?, success = 0
            WHERE version = ? AND success = 0
            """,
            (
                LIFECYCLE_RUNTIME_CHECKSUM,
                started_at,
                _now_iso(),
                LIFECYCLE_RUNTIME_MIGRATION,
            ),
        )
        if cursor.rowcount == 0:
            row = conn.execute(
                "SELECT success FROM schema_migrations WHERE version = ?",
                (LIFECYCLE_RUNTIME_MIGRATION,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO schema_migrations
                    (version, checksum, started_at, finished_at, success)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (
                        LIFECYCLE_RUNTIME_MIGRATION,
                        LIFECYCLE_RUNTIME_CHECKSUM,
                        started_at,
                        _now_iso(),
                    ),
                )
        conn.commit()
    except Exception:
        conn.rollback()


def _table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _column_exists(conn, table_name, column_name):
    return any(
        _pragma_column_name(row) == column_name
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    )


def _pragma_column_name(row):
    if _row_has_key(row, "name"):
        return row["name"]
    return row[1]


def _row_has_key(row, key):
    return hasattr(row, "keys") and key in row.keys()


def _value(row, key, index):
    if _row_has_key(row, key):
        return row[key]
    return row[index]


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
