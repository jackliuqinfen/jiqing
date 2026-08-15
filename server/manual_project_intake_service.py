"""Atomic manual project intake through the confirmed-contract boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from server.contract_fallback_service import (
    ContractFallbackError,
    create_direct_fallback_review,
    manual_contract_fields,
)
from server.document_requirements import applicable_required_categories
from server.document_review_service import (
    confirm_review_in_transaction,
    review_detail,
    save_decisions_in_transaction,
)
from server.project_intake_drafts import (
    ProjectIntakeDraftError,
    _validate_expected_revision,
    _validate_project_values,
    get_draft,
    save_draft,
)
from server.stage_fact_service import confirmation_result


_REQUIRED_CONTRACT_VALUES = {
    "project.name": "项目名称",
    "party.owner": "建设单位",
    "party.contractor": "施工单位",
    "contract.amount": "合同金额",
    "contract.signed_date": "合同签订日期",
    "contract.payment_terms": "付款条款",
}

_PROJECT_COLUMN_MAP = {
    "contractorName": "contractor_name",
    "contractorContact": "contractor_contact",
    "companyRole": "company_role",
    "settlementStatus": "settlement_status",
    "submittedAmount": "submitted_amount",
    "paidAmount": "paid_amount",
    "paymentTerms": "payment_terms",
    "plannedStartDate": "planned_start_date",
    "plannedEndDate": "planned_end_date",
    "description": "description",
}


class ManualProjectIntakeError(ValueError):
    """Request or domain validation failure for manual project intake."""

    def __init__(self, code, message, field=None):
        super().__init__(message)
        self.code = str(code)
        self.field = None if field is None else str(field)


def confirm_manual_project_intake(
    conn,
    *,
    document_version_id,
    contract_values,
    project_values,
    draft_id,
    expected_draft_revision,
    idempotency_key,
    form_template_version,
    actor,
    project_code_generator,
    operation_logger,
    storage=None,
    now=None,
):
    """Create a formal project, contract material, and completed draft atomically."""

    document_version_id = str(document_version_id or "").strip()
    draft_id = str(draft_id or "").strip()
    idempotency_key = str(idempotency_key or "").strip()
    form_template_version = str(form_template_version or "").strip()
    actor = _require_actor(actor)
    now = now or _now_iso()

    if not document_version_id:
        raise ManualProjectIntakeError(
            "contract_pdf_required", "请先保存合同 PDF。", "documentVersionId"
        )
    if not draft_id:
        raise ManualProjectIntakeError("draft_required", "请先保存项目草稿。", "draftId")
    if not idempotency_key:
        raise ManualProjectIntakeError(
            "idempotency_key_required", "确认操作必须提供幂等键。", "idempotencyKey"
        )
    if not form_template_version:
        raise ManualProjectIntakeError(
            "form_template_version_required",
            "确认操作必须绑定表单模板版本。",
            "formTemplateVersion",
        )
    if project_code_generator is None:
        raise ManualProjectIntakeError(
            "project_code_generator_required", "项目编号生成器不可用。"
        )
    if not callable(operation_logger):
        raise ManualProjectIntakeError(
            "operation_logger_required", "操作日志记录器不可用。"
        )

    try:
        expected_draft_revision = _validate_expected_revision(expected_draft_revision)
        clean_project_values = _validate_project_values(project_values)
        fields = manual_contract_fields(contract_values)
    except ProjectIntakeDraftError as exc:
        raise ManualProjectIntakeError(exc.code, str(exc)) from exc
    except ContractFallbackError as exc:
        raise ManualProjectIntakeError(exc.code, str(exc)) from exc

    clean_contract_values = dict(contract_values or {})
    _validate_required_contract_values(clean_contract_values)
    if not str(clean_project_values.get("paymentTerms") or "").strip():
        raise ManualProjectIntakeError(
            "confirmed_value_required", "确认前必须填写付款条款。", "paymentTerms"
        )

    review_key = f"manual-project-review:{idempotency_key}"
    confirmation_key = f"manual-project-confirm:{idempotency_key}"

    try:
        conn.execute("BEGIN IMMEDIATE")
        version = _document_version(conn, document_version_id)
        if not version:
            raise ManualProjectIntakeError(
                "document_version_not_found", "未找到合同文档版本。", "documentVersionId"
            )
        if version["document_type"] != "construction_contract":
            raise ManualProjectIntakeError(
                "contract_document_required", "所选文件不是施工合同。", "documentVersionId"
            )
        if str(version["mime_type"] or "").lower().split(";", 1)[0].strip() != "application/pdf":
            raise ManualProjectIntakeError(
                "contract_pdf_required", "项目建档必须保存 PDF 格式的合同原件。", "documentVersionId"
            )

        existing = _row(
            conn,
            """
            SELECT rj.document_version_id, dr.id AS review_id, dr.status AS review_status,
                   dr.confirmation_idempotency_key
            FROM recognition_jobs rj
            LEFT JOIN document_reviews dr ON dr.recognition_job_id = rj.id
            WHERE rj.idempotency_key = ?
            """,
            (review_key,),
        )
        if existing and existing["document_version_id"] != document_version_id:
            raise ManualProjectIntakeError(
                "fallback_idempotency_conflict",
                "人工复核幂等键已用于其他合同版本。",
                "idempotencyKey",
            )
        if existing and existing.get("review_id"):
            review_id = existing["review_id"]
            review = _row(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
        else:
            fallback = create_direct_fallback_review(
                conn,
                document_version_id=document_version_id,
                adapter_key="manual-entry",
                idempotency_key=review_key,
                fields=fields,
                actor=actor,
                fallback_reason="manual_selected",
                now=now,
            )
            review_id = fallback["review_id"]
            review = _row(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))

        # A retry after a successful commit must replay before inspecting the now-completed draft.
        if (
            review
            and review["status"] == "confirmed"
            and review.get("confirmation_idempotency_key") == confirmation_key
        ):
            result = confirmation_result(conn, review_id)
            conn.commit()
            return result

        draft = get_draft(conn, draft_id, owner_user_id=actor["id"])
        if not draft:
            raise ManualProjectIntakeError("draft_not_found", "未找到项目录入草稿。", "draftId")
        if draft["status"] not in {"draft", "document_attached"}:
            raise ManualProjectIntakeError("draft_immutable", "当前草稿不能继续修改。", "draftId")
        if draft["revision"] != expected_draft_revision:
            raise ManualProjectIntakeError(
                "draft_version_conflict", "草稿已在其他窗口更新，请刷新后继续。", "expectedDraftRevision"
            )
        if draft["document_version_id"] != document_version_id:
            raise ManualProjectIntakeError(
                "draft_document_mismatch", "草稿关联的合同版本与本次确认不一致。", "documentVersionId"
            )

        detail = review_detail(conn, review_id)
        fields_by_key = {item["semanticKey"]: item for item in detail["fields"]}
        for manual_field in fields:
            semantic_key = manual_field["semantic_key"]
            field = fields_by_key.get(semantic_key)
            if not field:
                raise ManualProjectIntakeError(
                    "manual_review_field_missing", f"人工复核字段不存在：{semantic_key}。", semantic_key
                )
            detail = save_decisions_in_transaction(
                conn,
                review_id=review_id,
                expected_review_version=detail["reviewVersion"],
                decisions=[{
                    "fieldId": field["id"],
                    "decision": "accepted",
                    "confirmedValue": field["aiValue"],
                }],
                actor=actor,
                now=now,
            )

        result = confirm_review_in_transaction(
            conn,
            review_id=review_id,
            expected_review_version=detail["reviewVersion"],
            idempotency_key=confirmation_key,
            actor=actor,
            allowed_project_ids=(),
            form_template_version=form_template_version,
            project_code_generator=project_code_generator,
            now=now,
        )
        project_id = result["projectId"]

        _promote_contract_storage(conn, project_id, version, storage)
        _link_original_contract(conn, project_id, version, actor, now)
        completion, missing = _document_rollup(conn, project_id, "contract_signed")
        _update_manual_project_values(
            conn,
            project_id,
            clean_project_values,
            completion=completion,
            missing=missing,
            actor=actor,
            now=now,
        )
        save_draft(
            conn,
            draft_id=draft_id,
            owner_user_id=actor["id"],
            expected_revision=expected_draft_revision,
            completed_project_id=project_id,
            now=now,
        )
        operation_logger(
            "manual_project_intake.confirm",
            "project_record",
            project_id,
            {
                "documentVersionId": document_version_id,
                "draftId": draft_id,
                "reviewId": review_id,
            },
        )
        result["project"] = _row(
            conn, "SELECT * FROM project_records WHERE id = ?", (project_id,)
        )
        result["replayed"] = False
        conn.commit()
        return result
    except ProjectIntakeDraftError as exc:
        conn.rollback()
        raise ManualProjectIntakeError(exc.code, str(exc)) from exc
    except ContractFallbackError as exc:
        conn.rollback()
        raise ManualProjectIntakeError(exc.code, str(exc)) from exc
    except Exception:
        conn.rollback()
        raise


def _validate_required_contract_values(values):
    for key, label in _REQUIRED_CONTRACT_VALUES.items():
        value = values.get(key)
        if _empty(value):
            raise ManualProjectIntakeError(
                "confirmed_value_required", f"确认前必须填写{label}。", key
            )
    amount = values.get("contract.amount")
    if type(amount) is not int or amount <= 0 or amount > 9_223_372_036_854_775_807:
        raise ManualProjectIntakeError(
            "contract_amount_invalid", "合同金额必须是大于零的整分金额。", "contract.amount"
        )
    terms = values.get("contract.payment_terms")
    if (
        not isinstance(terms, list)
        or not all(isinstance(item, str) for item in terms)
        or not any(item.strip() for item in terms)
    ):
        raise ManualProjectIntakeError(
            "confirmed_value_required", "确认前必须填写付款条款。", "contract.payment_terms"
        )


def _empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value or not any(isinstance(item, str) and item.strip() for item in value)
    return False


def _document_version(conn, version_id):
    return _row(
        conn,
        """
        SELECT dv.*, d.document_type, d.lifecycle_stage
        FROM document_versions dv
        JOIN documents d ON d.id = dv.document_id
        WHERE dv.id = ?
        """,
        (version_id,),
    )


def _link_original_contract(conn, project_id, version, actor, now):
    relative_path = str(version["relative_path"] or "")
    original_name = str(version["original_name"] or "合同原件.pdf")
    conn.execute(
        """
        INSERT INTO project_files
        (id, project_id, category_key, display_name, original_name, stored_name,
         file_ext, mime_type, file_size, relative_path, version_no, is_current,
         uploaded_by, uploaded_by_name, uploaded_at)
        VALUES (?, ?, 'contract', ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            project_id,
            original_name,
            original_name,
            Path(relative_path).name,
            Path(original_name).suffix.lower(),
            version["mime_type"],
            int(version["file_size"] or 0),
            relative_path,
            actor["id"],
            actor["name"],
            now,
        ),
    )


def _promote_contract_storage(conn, project_id, version, storage):
    """Move an unbound contract into the confirmed project's contract folder."""
    if storage is None:
        return
    document_id = str(version["document_id"] or "").strip()
    if not document_id:
        return
    versions = conn.execute(
        "SELECT id, version_no, relative_path FROM document_versions WHERE document_id = ?",
        (document_id,),
    ).fetchall()
    for item in versions:
        old_path = str(item["relative_path"] or "")
        if not old_path:
            continue
        new_path = (
            f"contract-records/{project_id}/{document_id}/v{int(item['version_no'])}/"
            f"{Path(old_path).parent.name}/{Path(old_path).name}"
        )
        storage.move(old_path, new_path)
        conn.execute(
            "UPDATE document_versions SET relative_path = ? WHERE id = ?",
            (new_path, item["id"]),
        )

        pages = conn.execute(
            "SELECT id, relative_path FROM document_pages WHERE document_version_id = ?",
            (item["id"],),
        ).fetchall()
        for page in pages:
            page_path = str(page["relative_path"] or "")
            if not page_path:
                continue
            page_name = Path(page_path).name
            page_new_path = (
                f"contract-records/{project_id}/{document_id}/v{int(item['version_no'])}/pages/{page_name}"
            )
            storage.move(page_path, page_new_path)
            conn.execute(
                "UPDATE document_pages SET relative_path = ? WHERE id = ?",
                (page_new_path, page["id"]),
            )


def _document_rollup(conn, project_id, project_stage):
    categories = conn.execute(
        "SELECT * FROM project_document_categories WHERE enabled = 1 AND required = 1"
    ).fetchall()
    required = applicable_required_categories(categories, project_stage)
    current = conn.execute(
        """
        SELECT DISTINCT category_key FROM project_files
        WHERE project_id = ? AND is_current = 1 AND COALESCE(is_deleted, 0) = 0
        """,
        (project_id,),
    ).fetchall()
    current_keys = {row["category_key"] for row in current}
    missing = sum(1 for category in required if category["category_key"] not in current_keys)
    total = max(len(required), 1)
    return round((total - missing) / total * 100), missing


def _update_manual_project_values(
    conn, project_id, values, *, completion, missing, actor, now
):
    assignments = ["document_completion = ?", "missing_required_count = ?"]
    params = [completion, missing]
    for key, column in _PROJECT_COLUMN_MAP.items():
        if key in values:
            assignments.append(f"{column} = ?")
            params.append(values[key])
    assignments.extend(["updated_by = ?", "updated_at = ?"])
    params.extend([actor["id"], now, project_id])
    conn.execute(
        f"UPDATE project_records SET {', '.join(assignments)} WHERE id = ?",
        params,
    )


def _require_actor(actor):
    actor_id = str((actor or {}).get("id") or "").strip()
    actor_name = str((actor or {}).get("name") or "").strip()
    if not actor_id or not actor_name:
        raise ManualProjectIntakeError("actor_required", "项目确认必须关联当前用户。")
    return {**dict(actor or {}), "id": actor_id, "name": actor_name}


def _row(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {item[0]: row[index] for index, item in enumerate(cursor.description)}


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
