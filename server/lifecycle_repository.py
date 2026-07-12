"""SQLite repository for project lifecycle transitions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from server.lifecycle import (
    audit_start_failures,
    contract_gate_failures,
    next_stage,
    stage_label,
    validate_adjacent_transition,
)
from server.migrations import apply_pending_migrations


class LifecycleRepositoryError(Exception):
    """Base class for lifecycle repository errors."""


class LifecycleNotFoundError(LifecycleRepositoryError):
    def __init__(self, project_id):
        super().__init__("Project not found")
        self.project_id = project_id
        self.code = "project_not_found"


class LifecycleConflictError(LifecycleRepositoryError):
    def __init__(self, expected_version, current_version):
        super().__init__("Lifecycle version conflict")
        self.expected_version = expected_version
        self.current_version = current_version
        self.code = "stale_lifecycle_version"


class LifecycleIdempotencyConflictError(LifecycleRepositoryError):
    def __init__(self, idempotency_key, existing_target_stage, requested_target_stage):
        super().__init__("Idempotency key conflicts with an existing target stage")
        self.idempotency_key = idempotency_key
        self.existing_target_stage = existing_target_stage
        self.requested_target_stage = requested_target_stage
        self.code = "idempotency_key_conflict"


class LifecycleBlockedError(LifecycleRepositoryError):
    def __init__(self, blockers):
        super().__init__("Lifecycle transition blocked")
        self.blockers = blockers
        self.code = "lifecycle_transition_blocked"


def lifecycle_snapshot(conn, project_id):
    """Return current lifecycle state, next transition, blockers, and recent events."""
    project = _fetch_project(conn, project_id)
    current_stage = _value(project, "project_status") or "awarded"
    version = int(_value(project, "lifecycle_version") or 0)
    target_stage = next_stage(current_stage)
    blockers = _transition_blockers(conn, project, target_stage) if target_stage else []
    events = [
        _event_payload(row)
        for row in _fetch_all_dicts(
            conn,
            """
            SELECT * FROM project_lifecycle_events
            WHERE project_id = ?
            ORDER BY created_at DESC, lifecycle_version DESC
            LIMIT 10
            """,
            (project_id,),
        )
    ]

    return {
        "projectId": project_id,
        "currentStage": current_stage,
        "currentStageLabel": stage_label(current_stage),
        "lifecycleVersion": version,
        "nextTransition": None if not target_stage else {
            "toStage": target_stage,
            "toStageLabel": stage_label(target_stage),
            "blockers": blockers,
        },
        "blockers": blockers,
        "recentEvents": events,
    }


def transition_project(
    conn,
    project_id,
    target_stage,
    expected_version,
    idempotency_key,
    reason="",
    actor=None,
):
    """Advance a project one lifecycle stage with version and idempotency checks."""
    if not idempotency_key or not str(idempotency_key).strip():
        raise ValueError("idempotency_key is required")

    actor = actor or {}
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing_event = _fetch_event_by_idempotency(conn, project_id, idempotency_key)
        if existing_event:
            existing_target_stage = _value(existing_event, "to_stage")
            if target_stage != existing_target_stage:
                raise LifecycleIdempotencyConflictError(
                    idempotency_key,
                    existing_target_stage,
                    target_stage,
                )
            conn.commit()
            return _transition_result(project_id, existing_event)

        project = _fetch_project(conn, project_id)
        current_version = int(_value(project, "lifecycle_version") or 0)
        if int(expected_version) != current_version:
            raise LifecycleConflictError(expected_version, current_version)

        blockers = _transition_blockers(conn, project, target_stage)
        if blockers:
            raise LifecycleBlockedError(blockers)

        current_stage = _value(project, "project_status") or "awarded"
        new_version = current_version + 1
        event_id = uuid.uuid4().hex
        created_at = _now_iso()
        actor_id = _actor_value(actor, "id")
        actor_name = _actor_value(actor, "name")
        payload_json = json.dumps({}, ensure_ascii=False, separators=(",", ":"))

        conn.execute(
            """
            UPDATE project_records
            SET project_status = ?, lifecycle_version = ?, updated_at = ?
            WHERE id = ?
            """,
            (target_stage, new_version, created_at, project_id),
        )
        conn.execute(
            """
            INSERT INTO project_lifecycle_events
            (id, project_id, from_stage, to_stage, transition_type, reason,
             idempotency_key, lifecycle_version, actor_id, actor_name, payload_json, created_at)
            VALUES (?, ?, ?, ?, 'forward', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                project_id,
                current_stage,
                target_stage,
                reason or "",
                idempotency_key,
                new_version,
                actor_id,
                actor_name,
                payload_json,
                created_at,
            ),
        )
        event = _fetch_event_by_id(conn, event_id)
        conn.commit()
        return _transition_result(project_id, event)
    except Exception:
        conn.rollback()
        raise


def _transition_blockers(conn, project, target_stage):
    current_stage = _value(project, "project_status") or "awarded"
    blockers = validate_adjacent_transition(current_stage, target_stage)
    if blockers:
        return blockers
    if target_stage == "contract_signed":
        blockers.extend(
            contract_gate_failures(
                project,
                has_contract_file=_has_current_contract_file(conn, _value(project, "id")),
            )
        )
    if target_stage == "first_audit":
        blockers.extend(audit_start_failures(project))
        if _value(project, "audit_project_id"):
            blockers.append({
                "code": "audit_progress_required",
                "field": "projectStatus",
                "message": "项目已关联审计流程，请从审计看板推进一审阶段。",
            })
        else:
            blockers.append({
                "code": "audit_link_required",
                "field": "auditProjectId",
                "message": "进入一审前必须先从项目详情发起审计流程。",
            })
    return blockers


def _fetch_project(conn, project_id):
    project = _fetch_one_dict(
        conn,
        "SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
        (project_id,),
    )
    if not project:
        raise LifecycleNotFoundError(project_id)
    return project


def _has_current_contract_file(conn, project_id):
    row = conn.execute(
        """
        SELECT 1 FROM project_files
        WHERE project_id = ?
          AND category_key = 'contract'
          AND COALESCE(is_current, 1) = 1
          AND COALESCE(is_deleted, 0) = 0
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()
    return row is not None


def _fetch_event_by_idempotency(conn, project_id, idempotency_key):
    return _fetch_one_dict(
        conn,
        """
        SELECT * FROM project_lifecycle_events
        WHERE project_id = ? AND idempotency_key = ?
        """,
        (project_id, idempotency_key),
    )


def _fetch_event_by_id(conn, event_id):
    return _fetch_one_dict(
        conn,
        "SELECT * FROM project_lifecycle_events WHERE id = ?",
        (event_id,),
    )


def _transition_result(project_id, event):
    current_stage = _value(event, "to_stage")
    return {
        "projectId": project_id,
        "currentStage": current_stage,
        "currentStageLabel": stage_label(current_stage),
        "lifecycleVersion": int(_value(event, "lifecycle_version") or 0),
        "event": _event_payload(event),
    }


def _event_payload(row):
    payload_json = _value(row, "payload_json") or "{}"
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError):
        payload = {}
    return {
        "id": _value(row, "id"),
        "projectId": _value(row, "project_id"),
        "fromStage": _value(row, "from_stage"),
        "fromStageLabel": stage_label(_value(row, "from_stage")),
        "toStage": _value(row, "to_stage"),
        "toStageLabel": stage_label(_value(row, "to_stage")),
        "transitionType": _value(row, "transition_type") or "forward",
        "reason": _value(row, "reason") or "",
        "idempotencyKey": _value(row, "idempotency_key"),
        "lifecycleVersion": int(_value(row, "lifecycle_version") or 0),
        "actorId": _value(row, "actor_id") or "",
        "actorName": _value(row, "actor_name") or "",
        "payload": payload,
        "createdAt": _value(row, "created_at"),
    }


def _fetch_one_dict(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_dict(cursor, row)


def _fetch_all_dicts(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    return [_row_to_dict(cursor, row) for row in cursor.fetchall()]


def _row_to_dict(cursor, row):
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {description[0]: row[index] for index, description in enumerate(cursor.description)}


def _value(mapping, key):
    return mapping.get(key) if mapping else None


def _actor_value(actor, key):
    if isinstance(actor, dict):
        return str(actor.get(key) or "")
    return ""


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
