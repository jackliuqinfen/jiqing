"""Owner-scoped drafts for resilient contract-driven project intake."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone

from server.recognition.schemas import schema_for_version


_EDITABLE_STATUSES = frozenset({"draft", "document_attached"})
_PROJECT_VALUE_KEYS = frozenset(
    {
        "contractorName",
        "contractorContact",
        "companyRole",
        "settlementStatus",
        "submittedAmount",
        "paidAmount",
        "paymentTerms",
        "plannedStartDate",
        "plannedEndDate",
        "description",
    }
)
_PROJECT_AMOUNT_KEYS = frozenset({"submittedAmount", "paidAmount"})
_UI_STATE_KEYS = frozenset(
    {"wizardStep", "pdfPage", "pdfScale", "previewCollapsed"}
)
_DEFAULT_UI_STATE = {
    "wizardStep": 0,
    "pdfPage": 1,
    "pdfScale": 1,
    "previewCollapsed": False,
}


class ProjectIntakeDraftError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = str(code)


def create_draft(
    conn,
    *,
    owner_user_id,
    values,
    project_values=None,
    ui_state=None,
    fallback_reason,
    fallback_note="",
    document_id=None,
    document_version_id=None,
    now=None,
):
    owner_user_id = str(owner_user_id or "").strip()
    fallback_reason = str(fallback_reason or "").strip()
    if not owner_user_id:
        raise ProjectIntakeDraftError("draft_owner_required", "草稿必须关联创建人。")
    if not fallback_reason:
        raise ProjectIntakeDraftError("fallback_reason_required", "请选择使用手工草稿的原因。")
    clean_values = _validate_values(values)
    clean_project_values = _validate_project_values(project_values)
    clean_ui_state = _validate_ui_state(ui_state)
    _validate_document_pair(conn, document_id, document_version_id)
    now = now or _now_iso()
    draft_id = uuid.uuid4().hex
    status = "document_attached" if document_id else "draft"
    conn.execute(
        """
        INSERT INTO project_intake_drafts
        (id, owner_user_id, status, document_id, document_version_id,
         schema_version, values_json, project_values_json, ui_state_json, revision,
         fallback_reason, fallback_note,
         completed_project_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'contract.v1', ?, ?, ?, 0, ?, ?, NULL, ?, ?)
        """,
        (
            draft_id,
            owner_user_id,
            status,
            document_id,
            document_version_id,
            _dump_values(clean_values),
            _dump_values(clean_project_values),
            _dump_values(clean_ui_state),
            fallback_reason,
            str(fallback_note or "").strip(),
            now,
            now,
        ),
    )
    return get_draft(conn, draft_id, owner_user_id=owner_user_id)


def list_drafts(conn, *, owner_user_id=None, include_all=False):
    if include_all:
        rows = conn.execute(
            "SELECT * FROM project_intake_drafts ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()
    else:
        owner_user_id = str(owner_user_id or "").strip()
        if not owner_user_id:
            return []
        rows = conn.execute(
            """
            SELECT * FROM project_intake_drafts
            WHERE owner_user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (owner_user_id,),
        ).fetchall()
    return [_map_row(row) for row in rows]


def get_draft(conn, draft_id, *, owner_user_id=None, include_all=False):
    if include_all:
        row = conn.execute(
            "SELECT * FROM project_intake_drafts WHERE id = ?", (str(draft_id),)
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM project_intake_drafts
            WHERE id = ? AND owner_user_id = ?
            """,
            (str(draft_id), str(owner_user_id or "")),
        ).fetchone()
    return _map_row(row) if row else None


def save_draft(
    conn,
    *,
    draft_id,
    owner_user_id,
    expected_revision,
    values=None,
    project_values=None,
    ui_state=None,
    fallback_reason=None,
    fallback_note=None,
    document_id=None,
    document_version_id=None,
    completed_project_id=None,
    now=None,
):
    draft = get_draft(conn, draft_id, owner_user_id=owner_user_id)
    if not draft:
        raise ProjectIntakeDraftError("draft_not_found", "未找到项目录入草稿。")
    if draft["status"] not in _EDITABLE_STATUSES:
        raise ProjectIntakeDraftError("draft_immutable", "当前草稿不能继续修改。")
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ProjectIntakeDraftError("draft_revision_invalid", "草稿版本必须是非负整数。")

    next_values = draft["values"] if values is None else _validate_values(values)
    next_project_values = (
        draft["project_values"]
        if project_values is None
        else _validate_project_values(project_values)
    )
    next_ui_state = draft["ui_state"] if ui_state is None else _validate_ui_state(ui_state)
    next_reason = draft["fallback_reason"] if fallback_reason is None else str(fallback_reason).strip()
    if not next_reason:
        raise ProjectIntakeDraftError("fallback_reason_required", "请选择使用手工草稿的原因。")
    next_note = draft["fallback_note"] if fallback_note is None else str(fallback_note or "").strip()
    next_document_id = draft["document_id"] if document_id is None else document_id
    next_version_id = draft["document_version_id"] if document_version_id is None else document_version_id
    _validate_document_pair(conn, next_document_id, next_version_id)

    status = "document_attached" if next_document_id else "draft"
    if completed_project_id:
        status = "completed"
    now = now or _now_iso()
    cursor = conn.execute(
        """
        UPDATE project_intake_drafts
        SET status = ?, document_id = ?, document_version_id = ?, values_json = ?,
            project_values_json = ?, ui_state_json = ?, fallback_reason = ?,
            fallback_note = ?, completed_project_id = ?, revision = revision + 1,
            updated_at = ?
        WHERE id = ? AND owner_user_id = ? AND revision = ?
        """,
        (
            status,
            next_document_id,
            next_version_id,
            _dump_values(next_values),
            _dump_values(next_project_values),
            _dump_values(next_ui_state),
            next_reason,
            next_note,
            completed_project_id,
            now,
            str(draft_id),
            str(owner_user_id),
            expected_revision,
        ),
    )
    if cursor.rowcount != 1:
        raise ProjectIntakeDraftError(
            "draft_version_conflict",
            "草稿已在其他窗口更新，请刷新后继续。",
        )
    return get_draft(conn, draft_id, owner_user_id=owner_user_id)


def abandon_draft(conn, *, draft_id, owner_user_id, now=None):
    draft = get_draft(conn, draft_id, owner_user_id=owner_user_id)
    if not draft:
        raise ProjectIntakeDraftError("draft_not_found", "未找到项目录入草稿。")
    if draft["status"] not in _EDITABLE_STATUSES:
        raise ProjectIntakeDraftError("draft_immutable", "当前草稿不能继续修改。")
    conn.execute(
        """
        UPDATE project_intake_drafts SET status = 'abandoned', updated_at = ?
        WHERE id = ? AND owner_user_id = ?
        """,
        (now or _now_iso(), str(draft_id), str(owner_user_id)),
    )
    return get_draft(conn, draft_id, owner_user_id=owner_user_id)


def _validate_values(values):
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise ProjectIntakeDraftError("draft_values_invalid", "合同草稿字段必须是对象。")
    allowed = schema_for_version("contract.v1").semantic_keys
    clean = {}
    for key, value in values.items():
        if key not in allowed:
            raise ProjectIntakeDraftError("draft_field_invalid", f"不支持的合同字段：{key}。")
        if value is None:
            clean[key] = None
        elif isinstance(value, bool) or not isinstance(value, (str, int, float, list)):
            raise ProjectIntakeDraftError("draft_value_invalid", f"合同字段 {key} 的值类型无效。")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ProjectIntakeDraftError("draft_value_invalid", f"合同字段 {key} 不能是非有限数值。")
        elif isinstance(value, list) and not all(isinstance(item, str) for item in value):
            raise ProjectIntakeDraftError("draft_value_invalid", f"合同字段 {key} 的列表只能包含文本。")
        else:
            clean[key] = value
    return clean


def _validate_project_values(values):
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise ProjectIntakeDraftError("project_values_invalid", "项目草稿字段必须是对象。")
    clean = {}
    for key, value in values.items():
        if key not in _PROJECT_VALUE_KEYS:
            raise ProjectIntakeDraftError("project_field_invalid", f"不支持的项目字段：{key}。")
        if key in _PROJECT_AMOUNT_KEYS:
            if value is None:
                clean[key] = None
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProjectIntakeDraftError(
                    "project_value_invalid", f"项目字段 {key} 必须是有限数值。"
                )
            elif not math.isfinite(value):
                raise ProjectIntakeDraftError(
                    "project_value_invalid", f"项目字段 {key} 必须是有限数值。"
                )
            else:
                clean[key] = value
        elif value is None or isinstance(value, str):
            clean[key] = value
        else:
            raise ProjectIntakeDraftError(
                "project_value_invalid", f"项目字段 {key} 必须是文本。"
            )
    return clean


def _validate_ui_state(values):
    if values is None:
        return dict(_DEFAULT_UI_STATE)
    if not isinstance(values, dict):
        raise ProjectIntakeDraftError("ui_state_invalid", "界面状态必须是对象。")
    unknown = set(values) - _UI_STATE_KEYS
    if unknown:
        key = sorted(unknown)[0]
        raise ProjectIntakeDraftError("ui_state_field_invalid", f"不支持的界面状态：{key}。")

    clean = {**_DEFAULT_UI_STATE, **values}
    wizard_step = clean["wizardStep"]
    if isinstance(wizard_step, bool) or not isinstance(wizard_step, int) or not 0 <= wizard_step <= 3:
        raise ProjectIntakeDraftError("ui_state_value_invalid", "向导步骤必须是 0 到 3 的整数。")
    pdf_page = clean["pdfPage"]
    if isinstance(pdf_page, bool) or not isinstance(pdf_page, int) or pdf_page < 1:
        raise ProjectIntakeDraftError("ui_state_value_invalid", "PDF 页码必须是大于等于 1 的整数。")
    pdf_scale = clean["pdfScale"]
    if (
        isinstance(pdf_scale, bool)
        or not isinstance(pdf_scale, (int, float))
        or not math.isfinite(pdf_scale)
        or not 0.5 <= pdf_scale <= 2.5
    ):
        raise ProjectIntakeDraftError("ui_state_value_invalid", "PDF 缩放比例必须在 0.5 到 2.5 之间。")
    if not isinstance(clean["previewCollapsed"], bool):
        raise ProjectIntakeDraftError("ui_state_value_invalid", "预览折叠状态必须是布尔值。")
    return clean


def _validate_document_pair(conn, document_id, document_version_id):
    if bool(document_id) != bool(document_version_id):
        raise ProjectIntakeDraftError("document_pair_required", "文档和文档版本必须同时提供。")
    if not document_id:
        return
    row = conn.execute(
        "SELECT document_id FROM document_versions WHERE id = ?",
        (str(document_version_id),),
    ).fetchone()
    if not row or str(row[0]) != str(document_id):
        raise ProjectIntakeDraftError("document_version_mismatch", "文档版本与所选文档不匹配。")


def _dump_values(values):
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _map_row(row):
    item = dict(row)
    values = _load_object(item.get("values_json"))
    project_values = _load_object(item.get("project_values_json"))
    try:
        ui_state = _validate_ui_state(_load_object(item.get("ui_state_json")))
    except ProjectIntakeDraftError:
        ui_state = dict(_DEFAULT_UI_STATE)
    return {
        "id": item["id"],
        "owner_user_id": item["owner_user_id"],
        "status": item["status"],
        "document_id": item.get("document_id"),
        "document_version_id": item.get("document_version_id"),
        "schema_version": item["schema_version"],
        "values": values,
        "project_values": project_values,
        "ui_state": ui_state,
        "revision": int(item.get("revision") or 0),
        "fallback_reason": item.get("fallback_reason") or "",
        "fallback_note": item.get("fallback_note") or "",
        "completed_project_id": item.get("completed_project_id"),
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def _load_object(value):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
