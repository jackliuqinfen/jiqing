"""Pure lifecycle policy for project-stage transitions.

This module intentionally has no database or HTTP dependencies so the same
rules can be used by repository and API layers.
"""

from decimal import Decimal, InvalidOperation

STAGE_ORDER = (
    "awarded",
    "contract_signed",
    "under_construction",
    "completed_acceptance",
    "pending_submission",
    "first_audit",
    "second_audit",
    "conclusion",
    "archived",
)

STAGE_LABELS = {
    "awarded": "已中标",
    "contract_signed": "已签订合同",
    "under_construction": "已进场施工中",
    "completed_acceptance": "已竣工验收",
    "pending_submission": "待报审",
    "first_audit": "一审中",
    "second_audit": "二审中",
    "conclusion": "已定案结论",
    "archived": "已归档",
}

AUDIT_START_STAGES = (
    "pending_submission",
    "first_audit",
    "second_audit",
)


def stage_label(stage):
    """Return the display label for a lifecycle stage."""
    return STAGE_LABELS.get(stage, stage or "")


def next_stage(stage):
    """Return the only permitted forward stage, or ``None`` at the end."""
    try:
        return STAGE_ORDER[STAGE_ORDER.index(stage) + 1]
    except (ValueError, IndexError):
        return None


def validate_adjacent_transition(current, target):
    """Return validation failures unless ``target`` is the next stage."""
    if current not in STAGE_ORDER:
        return [_failure(
            "invalid_current_stage",
            "currentStage",
            "当前项目阶段无效，不能推进生命周期。",
        )]
    if current == STAGE_ORDER[-1]:
        return [_failure(
            "terminal_stage",
            "toStage",
            "项目已归档，不能继续推进生命周期。",
        )]
    if target not in STAGE_ORDER:
        return [_failure(
            "invalid_target_stage",
            "toStage",
            "目标项目阶段无效。",
        )]
    if target != next_stage(current):
        return [_failure(
            "non_adjacent_transition",
            "toStage",
            "项目阶段只能按既定顺序逐步推进。",
        )]
    return []


def contract_gate_failures(project, has_contract_file):
    """Return all missing facts required before a contract can be signed."""
    failures = []
    if not _value(project, "contract_date", "contractDate"):
        failures.append(_failure(
            "contract_date_required",
            "contractDate",
            "签订合同前必须填写合同日期。",
        ))
    if _positive_number(_value(project, "contract_amount", "contractAmount")) <= Decimal("0"):
        failures.append(_failure(
            "contract_amount_required",
            "contractAmount",
            "签订合同前必须填写大于 0 的合同金额。",
        ))
    if not _value(project, "owner_unit", "ownerUnit"):
        failures.append(_failure(
            "owner_unit_required",
            "ownerUnit",
            "签订合同前必须填写建设单位。",
        ))
    if not _value(project, "construction_unit", "constructionUnit"):
        failures.append(_failure(
            "construction_unit_required",
            "constructionUnit",
            "签订合同前必须填写施工单位。",
        ))
    if not has_contract_file:
        failures.append(_failure(
            "contract_file_required",
            "contractFile",
            "签订合同前必须上传当前合同附件。",
        ))
    return failures


def audit_start_failures(project):
    """Return blockers for starting audit from a project record."""
    failures = []
    current_stage = _value(project, "project_status", "projectStatus")
    if current_stage not in AUDIT_START_STAGES:
        failures.append(_failure(
            "audit_stage_not_reached",
            "projectStatus",
            "项目未到送审阶段，不能发起审计。",
        ))
    if _positive_number(_value(project, "submitted_amount", "submittedAmount")) <= Decimal("0"):
        failures.append(_failure(
            "submitted_amount_required",
            "submittedAmount",
            "发起审计前必须填写大于 0 的送审金额。",
        ))
    return failures


def _failure(code, field, message):
    return {"code": code, "field": field, "message": message}


def _value(project, snake_case_key, camel_case_key):
    value = project.get(snake_case_key)
    if value is None or (isinstance(value, str) and not value.strip()):
        value = project.get(camel_case_key)
    return value.strip() if isinstance(value, str) else value


def _positive_number(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return Decimal("0")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    return number if number.is_finite() else Decimal("0")
