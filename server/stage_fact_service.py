"""Atomic writers for human-confirmed lifecycle evidence."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

from server.document_repository import mark_review_confirmed


class StageFactError(RuntimeError):
    """Base error for formal stage-fact writes."""


class StageFactBlockedError(StageFactError):
    def __init__(self, blockers):
        super().__init__("stage fact confirmation is blocked")
        self.blockers = list(blockers)


def create_project_from_confirmed_contract(
    conn,
    *,
    review,
    values,
    evidence_manifest,
    review_disposition,
    idempotency_key,
    actor,
    form_template_version,
    extraction_schema_version,
    project_code_generator,
    now,
):
    if project_code_generator is None:
        raise StageFactError("project code generator is required")
    required = {
        "project.name": "项目名称",
        "party.owner": "建设单位",
        "party.contractor": "施工单位",
        "contract.amount": "合同金额",
        "contract.signed_date": "合同签订日期",
        "contract.payment_terms": "付款条款",
    }
    blockers = _required_value_blockers(values, required)
    if blockers:
        raise StageFactBlockedError(blockers)

    duplicate = conn.execute(
        """
        SELECT pc.project_id
        FROM project_contracts pc
        JOIN document_versions existing_version
          ON existing_version.id = pc.document_version_id
        JOIN document_versions review_version
          ON review_version.id = ?
        WHERE existing_version.sha256 = review_version.sha256
        LIMIT 1
        """,
        (review["document_version_id"],),
    ).fetchone()
    if duplicate:
        raise StageFactBlockedError([
            _blocker(
                "duplicate_contract_document",
                "document",
                "该合同文件已经生成项目，不能重复建档。",
            )
        ])

    project_id = uuid.uuid4().hex
    project_code = project_code_generator(
        conn,
        values["contract.signed_date"],
        values["party.contractor"],
    )
    contract_amount_fen = _money_integer(values["contract.amount"], "contract.amount")
    if contract_amount_fen <= 0:
        raise StageFactBlockedError([
            _blocker("contract_amount_invalid", "contract.amount", "合同金额必须大于零。")
        ])
    conn.execute(
        """
        INSERT INTO project_records
        (id, project_code, project_name, contract_date, construction_unit,
         owner_unit, manager_name, project_status, lifecycle_version,
         contract_amount, payment_terms, created_by, updated_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'contract_signed', 1, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            project_code,
            values["project.name"],
            values["contract.signed_date"],
            values["party.contractor"],
            values["party.owner"],
            values.get("project.manager") or "",
            float(Decimal(contract_amount_fen) / Decimal(100)),
            _json(values["contract.payment_terms"]),
            _actor(actor, "id"),
            _actor(actor, "id"),
            now,
            now,
        ),
    )
    snapshot = _confirm_snapshot(
        conn,
        review=review,
        project_id=project_id,
        stage_key="contract_handoff",
        values=values,
        evidence_manifest=evidence_manifest,
        review_disposition=review_disposition,
        idempotency_key=idempotency_key,
        actor=actor,
        form_template_version=form_template_version,
        extraction_schema_version=extraction_schema_version,
        now=now,
    )
    contract_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO project_contracts
        (id, project_id, document_version_id, stage_form_snapshot_id,
         contract_name, contract_number, contract_type, owner_unit,
         contractor_unit, project_manager, contract_amount_fen, signed_date,
         start_date, end_date, payment_terms_json, retention_terms_json,
         performance_bond_terms_json, is_current, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            contract_id,
            project_id,
            review["document_version_id"],
            snapshot["id"],
            values.get("contract.name") or values["project.name"],
            values.get("contract.number") or "",
            values.get("contract.type") or "",
            values["party.owner"],
            values["party.contractor"],
            values.get("project.manager") or "",
            contract_amount_fen,
            values["contract.signed_date"],
            values.get("contract.start_date") or "",
            values.get("contract.end_date") or "",
            _json(values["contract.payment_terms"]),
            _json(values.get("contract.retention_terms") or []),
            _json(values.get("contract.performance_bond_terms") or []),
            now,
        ),
    )
    _insert_event(
        conn,
        project_id=project_id,
        from_stage="contract_handoff",
        to_stage="contract_signed",
        transition_type="project_created_from_contract",
        idempotency_key=idempotency_key,
        lifecycle_version=1,
        actor=actor,
        snapshot_id=snapshot["id"],
        document_version_id=review["document_version_id"],
        payload={"contractId": contract_id},
        now=now,
    )
    return {
        "status": "created",
        "replayed": False,
        "projectId": project_id,
        "project": _row(conn, "SELECT * FROM project_records WHERE id = ?", (project_id,)),
        "contract": _row(conn, "SELECT * FROM project_contracts WHERE id = ?", (contract_id,)),
        "snapshot": snapshot,
    }


def confirm_acceptance_fact(
    conn,
    *,
    review,
    project_id,
    values,
    evidence_manifest,
    review_disposition,
    idempotency_key,
    actor,
    form_template_version,
    extraction_schema_version,
    now,
):
    project = _project_for_stage(conn, project_id, "under_construction")
    conclusion = str(values.get("acceptance.conclusion") or "").strip()
    if not _acceptance_passed(conclusion):
        raise StageFactBlockedError([
            _blocker(
                "acceptance_not_passed",
                "acceptance.conclusion",
                "竣工验收未明确通过，不能形成验收事实或开放送审。",
            )
        ])
    required = {
        "acceptance.date": "竣工验收日期",
        "project.name": "项目名称",
        "party.contractor": "施工单位",
    }
    blockers = _required_value_blockers(values, required)
    if blockers:
        raise StageFactBlockedError(blockers)
    snapshot = _confirm_snapshot(
        conn,
        review=review,
        project_id=project_id,
        stage_key="completed_acceptance",
        values=values,
        evidence_manifest=evidence_manifest,
        review_disposition=review_disposition,
        idempotency_key=idempotency_key,
        actor=actor,
        form_template_version=form_template_version,
        extraction_schema_version=extraction_schema_version,
        now=now,
    )
    fact_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO project_acceptance_records
        (id, project_id, document_version_id, stage_form_snapshot_id,
         conclusion, acceptance_date, completion_date, contractor_unit,
         supervisor_unit, designer_unit, contract_amount_reference_fen,
         signature_status_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact_id,
            project_id,
            review["document_version_id"],
            snapshot["id"],
            conclusion,
            values["acceptance.date"],
            values.get("project.completion_date") or "",
            values.get("party.contractor") or "",
            values.get("party.supervisor") or "",
            values.get("party.designer") or "",
            _optional_integer(values.get("contract.amount_reference")),
            _json(values.get("acceptance.signatures") or []),
            now,
        ),
    )
    new_version = int(project["lifecycle_version"] or 0) + 1
    _advance_project(
        conn,
        project_id=project_id,
        expected_stage="under_construction",
        target_stage="completed_acceptance",
        expected_version=int(project["lifecycle_version"] or 0),
        target_version=new_version,
        now=now,
    )
    _insert_event(
        conn,
        project_id=project_id,
        from_stage="under_construction",
        to_stage="completed_acceptance",
        transition_type="forward",
        idempotency_key=idempotency_key,
        lifecycle_version=new_version,
        actor=actor,
        snapshot_id=snapshot["id"],
        document_version_id=review["document_version_id"],
        payload={"acceptanceRecordId": fact_id},
        now=now,
    )
    return {
        "status": "created",
        "replayed": False,
        "projectId": project_id,
        "acceptance": _row(
            conn, "SELECT * FROM project_acceptance_records WHERE id = ?", (fact_id,)
        ),
        "snapshot": snapshot,
    }


def confirm_final_determination_fact(
    conn,
    *,
    review,
    project_id,
    values,
    evidence_manifest,
    review_disposition,
    idempotency_key,
    actor,
    form_template_version,
    extraction_schema_version,
    now,
):
    project = _project_for_stage(conn, project_id, "second_audit")
    required = {
        "audit.engineering_determined_amount": "工程审定金额",
        "audit.final_settlement_amount": "最终结算金额",
        "audit.determination_date": "定案日期",
        "project.name": "项目名称",
        "party.owner": "建设单位",
        "party.contractor": "施工单位",
    }
    blockers = _required_value_blockers(values, required)
    if blockers:
        raise StageFactBlockedError(blockers)
    engineering = _money_integer(
        values["audit.engineering_determined_amount"],
        "audit.engineering_determined_amount",
    )
    fee = _money_integer(
        values.get("audit.review_fee_deduction") or 0,
        "audit.review_fee_deduction",
    )
    final = _money_integer(
        values["audit.final_settlement_amount"],
        "audit.final_settlement_amount",
    )
    if engineering - fee != final:
        raise StageFactBlockedError([
            _blocker(
                "final_settlement_equation_conflict",
                "audit.final_settlement_amount",
                "最终结算金额不等于工程审定金额减审核费用扣减。",
            )
        ])
    snapshot = _confirm_snapshot(
        conn,
        review=review,
        project_id=project_id,
        stage_key="conclusion",
        values=values,
        evidence_manifest=evidence_manifest,
        review_disposition=review_disposition,
        idempotency_key=idempotency_key,
        actor=actor,
        form_template_version=form_template_version,
        extraction_schema_version=extraction_schema_version,
        now=now,
    )
    fact_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO project_audit_determinations
        (id, project_id, document_version_id, stage_form_snapshot_id,
         audit_type, submitted_amount_fen, first_determined_amount_fen,
         second_determined_amount_fen, engineering_determined_amount_fen,
         review_fee_deduction_fen, final_settlement_amount_fen,
         reduction_amount_fen, reduction_rate_decimal, determination_date,
         uppercase_amount, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact_id,
            project_id,
            review["document_version_id"],
            snapshot["id"],
            values.get("audit.type") or "",
            _optional_integer(values.get("audit.submitted_amount")),
            _optional_integer(values.get("audit.first_determined_amount")),
            _optional_integer(values.get("audit.second_determined_amount")),
            engineering,
            fee,
            final,
            _optional_integer(values.get("audit.reduction_amount")),
            str(values.get("audit.reduction_rate") or ""),
            values["audit.determination_date"],
            str(values.get("audit.uppercase_amount") or ""),
            now,
        ),
    )
    new_version = int(project["lifecycle_version"] or 0) + 1
    _advance_project(
        conn,
        project_id=project_id,
        expected_stage="second_audit",
        target_stage="conclusion",
        expected_version=int(project["lifecycle_version"] or 0),
        target_version=new_version,
        now=now,
    )
    _insert_event(
        conn,
        project_id=project_id,
        from_stage="second_audit",
        to_stage="conclusion",
        transition_type="forward",
        idempotency_key=idempotency_key,
        lifecycle_version=new_version,
        actor=actor,
        snapshot_id=snapshot["id"],
        document_version_id=review["document_version_id"],
        payload={"determinationId": fact_id},
        now=now,
    )
    _insert_event(
        conn,
        project_id=project_id,
        from_stage="conclusion",
        to_stage="conclusion",
        transition_type="settlement_base_updated",
        idempotency_key=f"{idempotency_key}:settlement-base",
        lifecycle_version=new_version,
        actor=actor,
        snapshot_id=snapshot["id"],
        document_version_id=review["document_version_id"],
        payload={
            "determinationId": fact_id,
            "engineeringDeterminedAmountFen": engineering,
            "reviewFeeDeductionFen": fee,
            "finalSettlementAmountFen": final,
        },
        now=now,
    )
    return {
        "status": "created",
        "replayed": False,
        "projectId": project_id,
        "determination": _row(
            conn, "SELECT * FROM project_audit_determinations WHERE id = ?", (fact_id,)
        ),
        "snapshot": snapshot,
    }


def confirmation_result(conn, review_id):
    review = _row(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
    if not review or review["status"] != "confirmed":
        return None
    snapshot = _row(
        conn, "SELECT * FROM stage_form_snapshots WHERE review_id = ?", (review_id,)
    )
    result = {
        "status": "created",
        "replayed": True,
        "projectId": snapshot["project_id"],
        "snapshot": snapshot,
    }
    document = _row(conn, "SELECT document_type FROM documents WHERE id = ?", (review["document_id"],))
    table_key = {
        "construction_contract": ("project_contracts", "contract"),
        "completion_acceptance_certificate": ("project_acceptance_records", "acceptance"),
        "final_audit_determination": ("project_audit_determinations", "determination"),
    }.get(document["document_type"])
    if table_key:
        table, key = table_key
        result[key] = _row(
            conn,
            f"SELECT * FROM {table} WHERE stage_form_snapshot_id = ?",
            (snapshot["id"],),
        )
    if document["document_type"] == "construction_contract":
        result["project"] = _row(
            conn, "SELECT * FROM project_records WHERE id = ?", (snapshot["project_id"],)
        )
    return result


def _confirm_snapshot(
    conn,
    *,
    review,
    project_id,
    stage_key,
    values,
    evidence_manifest,
    review_disposition,
    idempotency_key,
    actor,
    form_template_version,
    extraction_schema_version,
    now,
):
    snapshot_values = dict(values)
    snapshot_values["_reviewDisposition"] = review_disposition
    return mark_review_confirmed(
        conn,
        review_id=review["id"],
        idempotency_key=idempotency_key,
        project_id=project_id,
        stage_key=stage_key,
        form_template_version=form_template_version,
        extraction_schema_version=extraction_schema_version,
        values=snapshot_values,
        evidence_manifest=evidence_manifest,
        reviewer_id=_actor(actor, "id"),
        reviewer_name=_actor(actor, "name"),
        now=now,
    )


def _project_for_stage(conn, project_id, expected_stage):
    project = _row(
        conn,
        "SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
        (project_id,),
    )
    if not project:
        raise StageFactBlockedError([
            _blocker("project_not_found", "projectId", "目标项目不存在。")
        ])
    if project["project_status"] != expected_stage:
        raise StageFactBlockedError([
            _blocker(
                "project_stage_incompatible",
                "projectStatus",
                "项目当前阶段不允许确认该业务凭证。",
            )
        ])
    return project


def _advance_project(
    conn,
    *,
    project_id,
    expected_stage,
    target_stage,
    expected_version,
    target_version,
    now,
):
    cursor = conn.execute(
        """
        UPDATE project_records
        SET project_status = ?, lifecycle_version = ?, updated_at = ?
        WHERE id = ? AND project_status = ? AND lifecycle_version = ?
        """,
        (target_stage, target_version, now, project_id, expected_stage, expected_version),
    )
    if cursor.rowcount != 1:
        raise StageFactBlockedError([
            _blocker(
                "project_lifecycle_conflict",
                "projectStatus",
                "项目阶段已被其他操作更新，请刷新后重试。",
            )
        ])


def _insert_event(
    conn,
    *,
    project_id,
    from_stage,
    to_stage,
    transition_type,
    idempotency_key,
    lifecycle_version,
    actor,
    snapshot_id,
    document_version_id,
    payload,
    now,
):
    conn.execute(
        """
        INSERT INTO project_lifecycle_events
        (id, project_id, from_stage, to_stage, transition_type, reason,
         idempotency_key, lifecycle_version, actor_id, actor_name, payload_json,
         stage_form_snapshot_id, evidence_document_version_id, created_at)
        VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            project_id,
            from_stage,
            to_stage,
            transition_type,
            idempotency_key,
            lifecycle_version,
            _actor(actor, "id"),
            _actor(actor, "name"),
            _json(payload),
            snapshot_id,
            document_version_id,
            now,
        ),
    )


def _required_value_blockers(values, required):
    return [
        _blocker("confirmed_value_required", key, f"确认前必须填写{label}。")
        for key, label in required.items()
        if values.get(key) in (None, "", [])
    ]


def _acceptance_passed(value):
    compact = value.replace(" ", "")
    if any(marker in compact for marker in ("不合格", "未通过", "不通过", "整改", "复验")):
        return False
    return "合格" in compact or "通过" in compact


def _money_integer(value, field):
    if isinstance(value, bool) or not isinstance(value, int):
        raise StageFactBlockedError([
            _blocker("money_value_invalid", field, "金额必须是精确到分的整数。")
        ])
    return value


def _optional_integer(value):
    return None if value in (None, "") else _money_integer(value, "amount")


def _actor(actor, key):
    return str((actor or {}).get(key) or "")


def _blocker(code, field, message):
    return {"code": code, "field": field, "message": message, "severity": "blocker"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _row(conn, sql, params=()):
    cursor = conn.execute(sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {item[0]: row[index] for index, item in enumerate(cursor.description)}
