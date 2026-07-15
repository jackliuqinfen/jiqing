"""Human review orchestration and the only formal document write boundary."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from datetime import date
from decimal import Decimal, InvalidOperation

from server.document_domain import critical_fields_for
from server.document_matching import validate_document_project_link
from server.document_repository import (
    DocumentNotFoundError,
    ReviewImmutableError,
    create_review,
    review_snapshot,
    upsert_review_decision,
)
from server.recognition.validators import build_review_blockers
from server.recognition.schemas import schema_for_version
from server.stage_fact_service import (
    StageFactBlockedError,
    confirmation_result,
    confirm_acceptance_fact,
    confirm_final_determination_fact,
    create_project_from_confirmed_contract,
)


class DocumentReviewServiceError(RuntimeError):
    """Base error for document-review operations."""


class ReviewVersionConflictError(DocumentReviewServiceError):
    def __init__(self, expected_version, current_version):
        super().__init__("review version conflict")
        self.expected_version = int(expected_version)
        self.current_version = int(current_version)


class ReviewDecisionValidationError(DocumentReviewServiceError):
    def __init__(self, code, field, message):
        super().__init__(message)
        self.code = code
        self.field = field


class CriticalBulkAcceptError(ReviewDecisionValidationError):
    def __init__(self, field):
        super().__init__(
            "critical_bulk_accept_denied",
            field,
            "关键字段必须逐项人工核对，不能批量接受。",
        )


class ReviewBlockedError(DocumentReviewServiceError):
    def __init__(self, blockers):
        super().__init__("review confirmation is blocked")
        self.blockers = list(blockers)


class ReviewProjectScopeError(DocumentReviewServiceError):
    pass


def open_review(
    conn,
    *,
    document_id,
    recognition_job_id,
    actor,
    allowed_project_ids,
    project_id=None,
    now=None,
):
    now = now or _now_iso()
    actor = _require_actor(actor)
    document = _row(conn, "SELECT * FROM documents WHERE id = ?", (document_id,))
    if not document:
        raise DocumentNotFoundError(document_id)
    if project_id and str(project_id) not in _project_scope(allowed_project_ids):
        raise ReviewProjectScopeError("project is outside the actor data scope")
    if document.get("project_id") and document["project_id"] != project_id:
        raise ReviewProjectScopeError("document is bound to another project")
    version_id = document.get("current_version_id")
    state = _field_state(conn, recognition_job_id)
    blockers = build_review_blockers(document["document_type"], state["validator_fields"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        review = create_review(
            conn,
            document_id=document_id,
            document_version_id=version_id,
            recognition_job_id=recognition_job_id,
            project_id=project_id,
            blockers=blockers,
            warnings=[],
            now=now,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return review_detail(conn, review["id"])


def save_decisions(
    conn,
    *,
    review_id,
    expected_review_version,
    decisions,
    actor,
    bulk=False,
    now=None,
):
    now = now or _now_iso()
    actor = _require_actor(actor)
    try:
        conn.execute("BEGIN IMMEDIATE")
        review = _mutable_review(conn, review_id, expected_review_version)
        state = _field_state(conn, review["recognition_job_id"])
        fields_by_id = {field["id"]: field for field in state["fields"]}
        normalized = [
            _normalize_decision(item, fields_by_id, review["document_id"])
            for item in list(decisions or [])
        ]
        document = _row(
            conn, "SELECT document_type FROM documents WHERE id = ?", (review["document_id"],)
        )
        critical = critical_fields_for(document["document_type"])
        critical_accepts = [
            item for item in normalized
            if item["decision"] == "accepted" and item["semantic_key"] in critical
        ]
        if critical_accepts and (bulk or len(normalized) > 1):
            raise CriticalBulkAcceptError(critical_accepts[0]["semantic_key"])

        for item in normalized:
            upsert_review_decision(
                conn,
                review_id=review_id,
                extracted_field_id=item["field_id"],
                decision=item["decision"],
                ai_value=item["ai_value"],
                confirmed_value=item["confirmed_value"],
                reviewer_id=actor["id"],
                reviewer_name=actor["name"],
                reason=item["reason"],
                now=now,
            )
        _refresh_review_issues(conn, review_id, now=now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return review_detail(conn, review_id)


def review_detail(conn, review_id):
    snapshot = review_snapshot(conn, review_id)
    document = _row(
        conn,
        """
        SELECT d.id, d.document_type, d.lifecycle_stage, d.project_id,
               d.candidate_project_id, d.status, dv.original_name, dv.mime_type,
               dv.file_size, dv.version_no
        FROM documents d
        JOIN document_versions dv ON dv.id = d.current_version_id
        WHERE d.id = ?
        """,
        (snapshot["document_id"],),
    )
    decision_by_field = {
        item["extracted_field_id"]: _decision_payload(item)
        for item in snapshot["decisions"]
    }
    anchors_by_field = {}
    for anchor in snapshot["anchors"]:
        anchors_by_field.setdefault(anchor["extracted_field_id"], []).append({
            "id": anchor["id"],
            "pageId": anchor["document_page_id"],
            "bbox": _loads(anchor["bbox_json"], []),
            "sourceText": anchor["source_text"],
        })
    fields = []
    for field in snapshot["fields"]:
        fields.append({
            "id": field["id"],
            "semanticKey": field["semantic_key"],
            "rawValue": field["raw_value"],
            "aiValue": _loads(field["normalized_value_json"], None),
            "confidence": field["confidence"],
            "validationStatus": field["validation_status"],
            "sourceKind": field["source_kind"],
            "anchors": anchors_by_field.get(field["id"], []),
            "decision": decision_by_field.get(field["id"]),
        })
    blockers = _loads(snapshot["blockers_json"], [])
    warnings = _loads(snapshot["warnings_json"], [])
    commands = []
    if snapshot["status"] != "confirmed":
        commands.append("save_decisions")
        if not blockers:
            commands.append("confirm")
    return {
        "id": snapshot["id"],
        "status": snapshot["status"],
        "reviewVersion": int(snapshot["review_version"] or 0),
        "projectId": snapshot.get("project_id"),
        "candidateProjectId": snapshot.get("candidate_project_id"),
        "reviewer": {
            "id": snapshot.get("reviewer_id") or "",
            "name": snapshot.get("reviewer_name") or "",
        },
        "document": {
            "id": document["id"],
            "type": document["document_type"],
            "lifecycleStage": document["lifecycle_stage"],
            "name": document["original_name"],
            "mimeType": document["mime_type"],
            "fileSize": int(document["file_size"]),
            "version": int(document["version_no"]),
        },
        "fields": fields,
        "blockers": blockers,
        "warnings": warnings,
        "allowedCommands": commands,
    }


def confirm_review(
    conn,
    *,
    review_id,
    expected_review_version,
    idempotency_key,
    actor,
    allowed_project_ids,
    form_template_version,
    project_id=None,
    project_code_generator=None,
    now=None,
):
    if not str(idempotency_key or "").strip():
        raise ReviewDecisionValidationError(
            "idempotency_key_required", "idempotencyKey", "确认操作必须提供幂等键。"
        )
    if not str(form_template_version or "").strip():
        raise ReviewDecisionValidationError(
            "form_template_version_required",
            "formTemplateVersion",
            "确认操作必须绑定表单模板版本。",
        )
    now = now or _now_iso()
    actor = _require_actor(actor)
    try:
        conn.execute("BEGIN IMMEDIATE")
        review = _row(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
        if not review:
            raise DocumentNotFoundError(review_id)
        if review["status"] == "confirmed":
            if review.get("confirmation_idempotency_key") != idempotency_key:
                raise ReviewImmutableError("confirmed review cannot be changed")
            result = confirmation_result(conn, review_id)
            conn.commit()
            return result
        _assert_review_version(review, expected_review_version)
        document = _row(conn, "SELECT * FROM documents WHERE id = ?", (review["document_id"],))
        target_project_id = project_id or review.get("project_id")
        scope = _project_scope(allowed_project_ids)
        state = _confirmation_state(conn, review)
        link_blockers = []
        if document["document_type"] != "construction_contract":
            if not target_project_id:
                link_blockers.append({
                    "code": "project_required",
                    "field": "projectId",
                    "message": "该阶段凭证必须关联已有项目。",
                    "severity": "blocker",
                })
            else:
                link_blockers.extend(
                    validate_document_project_link(
                        conn,
                        document["id"],
                        target_project_id,
                        allowed_project_ids=scope,
                        extracted_fields=state["effective_fields"],
                    )
                )
        blockers = [*state["blockers"], *link_blockers]
        if blockers:
            raise ReviewBlockedError(blockers)
        disposition = {
            "blockers": [],
            "warnings": state["warnings"],
            "reviewVersion": int(review["review_version"]),
            "confirmedBy": {"id": actor["id"], "name": actor["name"]},
        }
        kwargs = {
            "review": review,
            "values": state["values"],
            "evidence_manifest": state["evidence_manifest"],
            "review_disposition": disposition,
            "idempotency_key": idempotency_key,
            "actor": actor,
            "form_template_version": form_template_version,
            "extraction_schema_version": state["schema_version"],
            "now": now,
        }
        if document["document_type"] == "construction_contract":
            result = create_project_from_confirmed_contract(
                conn,
                project_code_generator=project_code_generator,
                **kwargs,
            )
        elif document["document_type"] == "completion_acceptance_certificate":
            result = confirm_acceptance_fact(
                conn,
                project_id=target_project_id,
                **kwargs,
            )
        elif document["document_type"] == "final_audit_determination":
            result = confirm_final_determination_fact(
                conn,
                project_id=target_project_id,
                **kwargs,
            )
        else:
            raise ReviewDecisionValidationError(
                "unsupported_document_type",
                "documentType",
                "该文件类型暂不支持形成正式业务事实。",
            )
        conn.commit()
        return result
    except StageFactBlockedError as exc:
        conn.rollback()
        raise ReviewBlockedError(exc.blockers) from exc
    except Exception:
        conn.rollback()
        raise


def _mutable_review(conn, review_id, expected_review_version):
    review = _row(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
    if not review:
        raise DocumentNotFoundError(review_id)
    if review["status"] == "confirmed":
        raise ReviewImmutableError("confirmed review cannot be changed")
    _assert_review_version(review, expected_review_version)
    return review


def _assert_review_version(review, expected_review_version):
    current = int(review["review_version"] or 0)
    if int(expected_review_version) != current:
        raise ReviewVersionConflictError(expected_review_version, current)


def _normalize_decision(item, fields_by_id, document_id):
    field_id = str((item or {}).get("fieldId") or "")
    field = fields_by_id.get(field_id)
    if not field:
        raise ReviewDecisionValidationError(
            "review_field_not_found", "fieldId", "复核字段不存在或不属于当前文件。"
        )
    decision = str(item.get("decision") or "").strip()
    if decision not in {"accepted", "modified", "rejected", "unrecognized"}:
        raise ReviewDecisionValidationError(
            "invalid_review_decision", field["semantic_key"], "复核决定无效。"
        )
    ai_value = field["normalized_value"]
    confirmed_value = item.get("confirmedValue")
    reason = str(item.get("reason") or "").strip()
    if decision == "accepted":
        if confirmed_value != ai_value:
            raise ReviewDecisionValidationError(
                "accepted_value_must_match_ai",
                field["semantic_key"],
                "接受识别值时不能修改内容；需要修改请使用“修改”并填写原因。",
            )
        confirmed_value = ai_value
    elif decision == "modified":
        if confirmed_value in (None, ""):
            raise ReviewDecisionValidationError(
                "modified_value_required", field["semantic_key"], "修改后必须填写确认值。"
            )
        if not reason:
            raise ReviewDecisionValidationError(
                "modified_reason_required", field["semantic_key"], "修改识别值必须填写原因。"
            )
    else:
        confirmed_value = None
    return {
        "field_id": field_id,
        "semantic_key": field["semantic_key"],
        "decision": decision,
        "ai_value": ai_value,
        "confirmed_value": confirmed_value,
        "reason": reason,
        "document_id": document_id,
    }


def _refresh_review_issues(conn, review_id, *, now):
    review = _row(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
    state = _field_state(conn, review["recognition_job_id"])
    decisions = _decision_map(conn, review_id)
    document = _row(conn, "SELECT document_type FROM documents WHERE id = ?", (review["document_id"],))
    effective_fields = _effective_validator_fields(state, decisions)
    blockers = build_review_blockers(
        document["document_type"],
        effective_fields,
        reviewer_decisions=decisions,
    )
    conn.execute(
        "UPDATE document_reviews SET blockers_json = ?, updated_at = ? WHERE id = ?",
        (_json(blockers), now, review_id),
    )


def _confirmation_state(conn, review):
    state = _field_state(conn, review["recognition_job_id"])
    decisions = _decision_map(conn, review["id"])
    document = _row(conn, "SELECT document_type FROM documents WHERE id = ?", (review["document_id"],))
    effective_fields = _effective_validator_fields(state, decisions)
    blockers = build_review_blockers(
        document["document_type"],
        effective_fields,
        reviewer_decisions=decisions,
    )
    values = {}
    evidence_manifest = {}
    for field in state["fields"]:
        decision = decisions.get(field["semantic_key"])
        if decision and decision["decision"] in {"accepted", "modified"}:
            values[field["semantic_key"]] = decision["confirmed_value"]
            evidence_manifest[field["semantic_key"]] = [
                anchor["id"] for anchor in field["anchors"]
            ]
    job = _row(conn, "SELECT schema_version FROM recognition_jobs WHERE id = ?", (review["recognition_job_id"],))
    return {
        "blockers": blockers,
        "warnings": _loads(review.get("warnings_json"), []),
        "values": values,
        "evidence_manifest": evidence_manifest,
        "schema_version": job["schema_version"],
        "effective_fields": effective_fields,
    }


def _field_state(conn, recognition_job_id):
    job = _row(
        conn,
        "SELECT schema_version FROM recognition_jobs WHERE id = ?",
        (recognition_job_id,),
    )
    rows = _rows(
        conn,
        "SELECT * FROM extracted_fields WHERE recognition_job_id = ? ORDER BY semantic_key, id",
        (recognition_job_id,),
    )
    anchors = _rows(
        conn,
        """
        SELECT ea.* FROM evidence_anchors ea
        JOIN extracted_fields ef ON ef.id = ea.extracted_field_id
        WHERE ef.recognition_job_id = ? ORDER BY ea.document_page_id, ea.id
        """,
        (recognition_job_id,),
    )
    by_field = {}
    for anchor in anchors:
        by_field.setdefault(anchor["extracted_field_id"], []).append(anchor)
    fields = []
    validator_fields = []
    for row in rows:
        normalized = _loads(row["normalized_value_json"], None)
        item = {
            **row,
            "normalized_value": normalized,
            "anchors": by_field.get(row["id"], []),
        }
        fields.append(item)
        validator_fields.append({
            "semantic_key": row["semantic_key"],
            "normalized_value": normalized,
            "validation_status": row["validation_status"],
            "anchors": item["anchors"],
        })
    return {
        "fields": fields,
        "validator_fields": validator_fields,
        "schema_version": job["schema_version"] if job else "",
    }


def _effective_validator_fields(state, decisions):
    schema = schema_for_version(state["schema_version"])
    effective = []
    for field in state["validator_fields"]:
        item = dict(field)
        decision = decisions.get(field["semantic_key"])
        if decision and decision["decision"] in {"accepted", "modified"}:
            item["normalized_value"] = decision["confirmed_value"]
            item["validation_status"] = _typed_value_status(
                decision["confirmed_value"],
                schema.field_types[field["semantic_key"]],
            )
        elif decision and decision["decision"] in {"rejected", "unrecognized"}:
            item["normalized_value"] = None
            # A reviewer may explicitly reject an optional OCR field. This is
            # different from a normalization failure; critical-field checks
            # below still block rejected required facts.
            item["validation_status"] = "valid"
        effective.append(item)
    return effective


def _typed_value_status(value, field_type):
    try:
        if field_type in {"money", "money_uppercase"}:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError
        elif field_type == "date":
            if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                raise ValueError
        elif field_type == "percentage":
            parsed = Decimal(str(value))
            if not parsed.is_finite() or parsed < 0:
                raise ValueError
        elif field_type == "clauses":
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise ValueError
        elif not isinstance(value, str) or not value.strip():
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        return "invalid"
    return "valid"


def _decision_map(conn, review_id):
    rows = _rows(
        conn,
        """
        SELECT rd.*, ef.semantic_key
        FROM review_decisions rd
        JOIN extracted_fields ef ON ef.id = rd.extracted_field_id
        WHERE rd.review_id = ?
        """,
        (review_id,),
    )
    return {
        row["semantic_key"]: {
            "decision": row["decision"],
            "ai_value": _loads(row["ai_value_json"], None),
            "confirmed_value": _loads(row["confirmed_value_json"], None),
            "reason": row["reason"],
        }
        for row in rows
    }


def _decision_payload(row):
    return {
        "decision": row["decision"],
        "aiValue": _loads(row["ai_value_json"], None),
        "confirmedValue": _loads(row["confirmed_value_json"], None),
        "reason": row["reason"],
        "reviewer": {"id": row["reviewer_id"], "name": row["reviewer_name"]},
    }


def _require_actor(actor):
    result = {
        "id": str((actor or {}).get("id") or "").strip(),
        "name": str((actor or {}).get("name") or "").strip(),
    }
    if not result["id"] or not result["name"]:
        raise ReviewDecisionValidationError(
            "reviewer_required", "reviewer", "复核操作必须记录当前用户身份。"
        )
    return result


def _project_scope(project_ids):
    return {str(item) for item in (project_ids or ()) if item}


def _row(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {item[0]: row[index] for index, item in enumerate(cursor.description)}


def _rows(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    result = []
    for row in cursor.fetchall():
        if hasattr(row, "keys"):
            result.append({key: row[key] for key in row.keys()})
        else:
            result.append({item[0]: row[index] for index, item in enumerate(cursor.description)})
    return result


def _loads(value, fallback):
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return fallback


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
