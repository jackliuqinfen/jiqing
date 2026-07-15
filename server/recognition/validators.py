"""Deterministic review blockers for normalized Phase 1 extraction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from server.document_domain import critical_fields_for


def validate_extracted_fields(document_type, fields, current_project_facts=None):
    field_map = {field["semantic_key"]: field for field in fields}
    issues = []
    for field in fields:
        if field.get("validation_status") == "invalid":
            issues.append(
                _issue(
                    "field_normalization_failed",
                    field["semantic_key"],
                    "识别结果无法转换为该字段要求的数据类型。",
                )
            )
    if document_type == "completion_acceptance_certificate":
        issues.extend(_validate_acceptance(field_map))
    elif document_type == "final_audit_determination":
        issues.extend(_validate_final_determination(field_map))
    return issues


def build_review_blockers(
    document_type,
    fields,
    *,
    reviewer_decisions=None,
    current_project_facts=None,
):
    blockers = validate_extracted_fields(
        document_type, fields, current_project_facts=current_project_facts
    )
    field_map = {field["semantic_key"]: field for field in fields}
    decisions = reviewer_decisions or {}
    for semantic_key in sorted(critical_fields_for(document_type)):
        field = field_map.get(semantic_key)
        decision = decisions.get(semantic_key) or {}
        if not field or field.get("normalized_value") is None:
            blockers.append(
                _issue(
                    "critical_field_missing",
                    semantic_key,
                    "关键字段未识别，必须人工补充。",
                )
            )
            continue
        requires_ocr_anchor = field.get("source_kind") not in {"manual", "external_ai"}
        if requires_ocr_anchor and not field.get("anchors") and decision.get("decision") != "modified":
            blockers.append(
                _issue(
                    "evidence_anchor_missing",
                    semantic_key,
                    "关键字段缺少原文件证据位置。",
                )
            )
        if decision.get("decision") not in {"accepted", "modified"}:
            blockers.append(
                _issue(
                    "critical_field_unresolved",
                    semantic_key,
                    "关键字段必须逐项人工确认。",
                )
            )
    return _deduplicate(blockers)


def _validate_acceptance(fields):
    issues = []
    completion = _value(fields, "project.completion_date")
    acceptance = _value(fields, "acceptance.date")
    if completion and acceptance:
        try:
            if date.fromisoformat(acceptance) < date.fromisoformat(completion):
                issues.append(
                    _issue(
                        "acceptance_before_completion",
                        "acceptance.date",
                        "验收日期不能早于竣工日期。",
                    )
                )
        except ValueError:
            pass
    conclusion = str(_value(fields, "acceptance.conclusion") or "").strip()
    if conclusion and not _is_passed_acceptance(conclusion):
        issues.append(
            _issue(
                "acceptance_not_passed",
                "acceptance.conclusion",
                "验收未明确通过，不能开放送审流程。",
            )
        )
    return issues


def _validate_final_determination(fields):
    issues = []
    submitted = _money(fields, "audit.submitted_amount")
    engineering = _money(fields, "audit.engineering_determined_amount")
    fee = _money(fields, "audit.review_fee_deduction")
    final = _money(fields, "audit.final_settlement_amount")
    reduction = _money(fields, "audit.reduction_amount")
    uppercase = _money(fields, "audit.uppercase_amount")

    if final is not None and uppercase is not None and final != uppercase:
        issues.append(
            _issue(
                "uppercase_amount_mismatch",
                "audit.uppercase_amount",
                "中文大写金额与最终结算金额不一致。",
            )
        )
    if submitted is not None and engineering is not None and reduction is not None:
        if submitted - engineering != reduction:
            issues.append(
                _issue(
                    "reduction_amount_equation_conflict",
                    "audit.reduction_amount",
                    "核减金额不等于送审金额减工程审定金额。",
                )
            )
    if engineering is not None and fee is not None and final is not None:
        if engineering - fee != final:
            issues.append(
                _issue(
                    "final_settlement_equation_conflict",
                    "audit.final_settlement_amount",
                    "最终结算金额不等于工程审定金额减审核费用扣减。",
                )
            )
    rate_value = _value(fields, "audit.reduction_rate")
    if submitted and reduction is not None and rate_value not in (None, ""):
        try:
            supplied = Decimal(str(rate_value))
            calculated = Decimal(reduction) / Decimal(submitted)
            if abs(supplied - calculated) > Decimal("0.0001"):
                code = (
                    "suspected_percentage_decimal_error"
                    if _is_factor_hundred(supplied, calculated)
                    else "reduction_rate_mismatch"
                )
                issues.append(
                    _issue(code, "audit.reduction_rate", "核减率与金额计算结果不一致。")
                )
        except (InvalidOperation, ZeroDivisionError):
            pass
    return issues


def _is_passed_acceptance(value):
    compact = value.replace(" ", "")
    rejected_markers = ("不合格", "未通过", "不通过", "整改", "复验")
    if any(marker in compact for marker in rejected_markers):
        return False
    return "合格" in compact or "通过" in compact


def _is_factor_hundred(left, right):
    if left == 0 or right == 0:
        return False
    ratio = abs(left / right)
    return abs(ratio - Decimal("100")) < Decimal("0.01") or abs(
        ratio - Decimal("0.01")
    ) < Decimal("0.0001")


def _money(fields, key):
    value = _value(fields, key)
    return None if value is None else int(value)


def _value(fields, key):
    field = fields.get(key)
    return None if not field else field.get("normalized_value")


def _issue(code, field, message):
    return {"code": code, "field": field, "message": message, "severity": "blocker"}


def _deduplicate(issues):
    seen = set()
    result = []
    for issue in issues:
        key = (issue["code"], issue["field"])
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result
