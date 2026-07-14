"""Explainable project recommendations and hard evidence-link blockers."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class MatchCandidate:
    project_id: str
    project_code: str
    project_name: str
    score: int
    contributions: tuple[str, ...]
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class MatchResult:
    candidates: tuple[MatchCandidate, ...]
    recommendation: MatchCandidate | None
    blockers: tuple[dict, ...]
    auto_confirmed: bool = False


def match_document_to_projects(conn, extracted_fields, *, allowed_project_ids):
    values = {
        _field_value(field, "semantic_key"): _field_value(
            field, "normalized_value"
        )
        for field in extracted_fields
        if _field_value(field, "semantic_key")
    }
    project_scope = tuple(
        sorted({str(project_id) for project_id in allowed_project_ids if project_id})
    )
    if not project_scope:
        return MatchResult(
            candidates=(),
            recommendation=None,
            blockers=(
                _blocker(
                    "project_scope_empty",
                    "projectId",
                    "当前用户没有可关联的项目。",
                ),
            ),
            auto_confirmed=False,
        )
    placeholders = ",".join("?" for _ in project_scope)
    rows = conn.execute(
        f"""
        SELECT id, project_code, project_name, owner_unit, construction_unit,
               project_status, contract_amount
        FROM project_records
        WHERE COALESCE(is_deleted, 0) = 0
          AND id IN ({placeholders})
        ORDER BY project_name, id
        """,
        project_scope,
    ).fetchall()
    candidates = tuple(
        sorted(
            (_score_candidate(dict(row), values) for row in rows),
            key=lambda item: (-item.score, item.project_id),
        )
    )
    blockers = []
    supplied_code = _text(values.get("project.code"))
    if supplied_code and not any(
        _normalize_code(item.project_code) == _normalize_code(supplied_code)
        for item in candidates
    ):
        blockers.append(
            _blocker(
                "project_code_mismatch",
                "project.code",
                "文件中的项目编号与现有项目不一致。",
            )
        )

    identity_candidates = [
        item
        for item in candidates
        if "project_code_exact" in item.contributions
        or "project_name_normalized" in item.contributions
    ]
    for candidate in identity_candidates:
        for conflict in candidate.conflicts:
            blockers.append(_candidate_conflict(conflict, candidate.project_id))

    eligible = [item for item in candidates if item.score >= 50 and not item.conflicts]
    recommendation = None
    if eligible:
        highest = eligible[0].score
        tied = [item for item in eligible if item.score == highest]
        if len(tied) == 1:
            recommendation = tied[0]
        else:
            blockers.append(
                _blocker(
                    "ambiguous_project_match",
                    "project.name",
                    "多个项目与文件信息同样匹配，必须人工选择。",
                )
            )
    return MatchResult(
        candidates=candidates,
        recommendation=recommendation if not blockers else None,
        blockers=tuple(_deduplicate_blockers(blockers)),
        auto_confirmed=False,
    )


def validate_document_project_link(
    conn,
    document_id,
    project_id,
    *,
    allowed_project_ids,
    extracted_fields=None,
):
    project_scope = {
        str(allowed_project_id)
        for allowed_project_id in allowed_project_ids
        if allowed_project_id
    }
    if str(project_id) not in project_scope:
        return [
            _blocker(
                "project_outside_scope",
                "projectId",
                "当前用户无权关联该项目。",
            )
        ]
    document = conn.execute(
        """
        SELECT d.*, dv.sha256
        FROM documents d
        JOIN document_versions dv ON dv.id = d.current_version_id
        WHERE d.id = ?
        """,
        (document_id,),
    ).fetchone()
    project = conn.execute(
        "SELECT * FROM project_records WHERE id = ? AND COALESCE(is_deleted, 0) = 0",
        (project_id,),
    ).fetchone()
    if not document or not project:
        return [
            _blocker(
                "document_or_project_missing",
                "projectId",
                "文件或目标项目不存在。",
            )
        ]
    document = dict(document)
    project = dict(project)
    blockers = []
    bound_project = document.get("project_id") or document.get("candidate_project_id")
    if bound_project and bound_project != project_id:
        blockers.append(
            _blocker(
                "document_project_conflict",
                "projectId",
                "该文件已绑定到另一个项目。",
            )
        )
    duplicate = conn.execute(
        """
        SELECT d.id
        FROM documents d
        JOIN document_versions dv ON dv.id = d.current_version_id
        WHERE d.id <> ? AND d.status = 'confirmed' AND dv.sha256 = ?
          AND COALESCE(d.project_id, '') <> COALESCE(?, '')
        LIMIT 1
        """,
        (document_id, document["sha256"], project_id),
    ).fetchone()
    if duplicate:
        blockers.append(
            _blocker(
                "duplicate_confirmed_hash",
                "document",
                "相同文件已在另一个项目中确认，不能重复关联。",
            )
        )
    if not _stage_compatible(document["document_type"], project.get("project_status")):
        blockers.append(
            _blocker(
                "stage_incompatible",
                "projectStatus",
                "目标项目当前阶段不允许确认该类文件。",
            )
        )

    fields = (
        list(extracted_fields)
        if extracted_fields is not None
        else _latest_fields(conn, document["current_version_id"])
    )
    if fields:
        match = match_document_to_projects(
            conn, fields, allowed_project_ids=project_scope
        )
        target = next(
            (item for item in match.candidates if item.project_id == project_id), None
        )
        if target:
            blockers.extend(
                _candidate_conflict(conflict, project_id)
                for conflict in target.conflicts
            )
        if match.recommendation and match.recommendation.project_id != project_id:
            blockers.append(
                _blocker(
                    "target_project_not_recommended",
                    "projectId",
                    "文件身份信息指向另一个项目，不能确认到当前项目。",
                )
            )
        elif not match.recommendation and _has_project_identity(fields):
            blockers.append(
                _blocker(
                    "project_identity_unverified",
                    "projectId",
                    "文件身份信息不足以唯一确认当前项目。",
                )
            )
        blockers.extend(match.blockers)
    return _deduplicate_blockers(blockers)


def _score_candidate(project, values):
    score = 0
    contributions = []
    conflicts = []
    supplied_code = _text(values.get("project.code"))
    if supplied_code:
        if _normalize_code(supplied_code) == _normalize_code(project["project_code"]):
            score += 100
            contributions.append("project_code_exact")
        else:
            conflicts.append("project_code_mismatch")

    supplied_name = _text(values.get("project.name"))
    if supplied_name and _normalize_project_name(supplied_name) == _normalize_project_name(
        project["project_name"]
    ):
        score += 50
        contributions.append("project_name_normalized")

    owner = _text(values.get("party.owner"))
    contractor = _text(values.get("party.contractor"))
    owner_matches = not owner or _normalize_organization(owner) == _normalize_organization(
        project.get("owner_unit")
    )
    contractor_matches = not contractor or _normalize_organization(
        contractor
    ) == _normalize_organization(project.get("construction_unit"))
    if owner and owner_matches:
        score += 20
        contributions.append("owner_exact")
    if contractor and contractor_matches:
        score += 20
        contributions.append("contractor_exact")
    if owner and contractor and not owner_matches and not contractor_matches:
        conflicts.append("both_parties_mismatch")

    supplied_amount = _first_money(values)
    project_amount = _project_amount_fen(project.get("contract_amount"))
    if supplied_amount and project_amount:
        ratio = Decimal(supplied_amount) / Decimal(project_amount)
        if ratio >= Decimal("10") or ratio <= Decimal("0.1"):
            conflicts.append("amount_magnitude_conflict")
        elif abs(ratio - Decimal("1")) <= Decimal("0.01"):
            score += 15
            contributions.append("contract_amount_close")
        elif abs(ratio - Decimal("1")) <= Decimal("0.1"):
            score += 8
            contributions.append("contract_amount_similar")

    return MatchCandidate(
        project_id=project["id"],
        project_code=project["project_code"],
        project_name=project["project_name"],
        score=score,
        contributions=tuple(contributions),
        conflicts=tuple(sorted(set(conflicts))),
    )


def _latest_fields(conn, document_version_id):
    job = conn.execute(
        """
        SELECT id FROM recognition_jobs
        WHERE document_version_id = ? AND status = 'review_ready'
        ORDER BY finished_at DESC, created_at DESC LIMIT 1
        """,
        (document_version_id,),
    ).fetchone()
    if not job:
        return []
    result = []
    for row in conn.execute(
        "SELECT semantic_key, raw_value, normalized_value_json FROM extracted_fields WHERE recognition_job_id = ?",
        (job["id"],),
    ).fetchall():
        try:
            normalized = json.loads(row["normalized_value_json"])
        except (TypeError, ValueError):
            normalized = None
        result.append(
            {
                "semantic_key": row["semantic_key"],
                "raw_value": row["raw_value"],
                "normalized_value": normalized,
            }
        )
    return result


def _stage_compatible(document_type, project_status):
    allowed = {
        "construction_contract": {"awarded", "contract_signed"},
        "completion_acceptance_certificate": {
            "under_construction",
            "completed_acceptance",
        },
        "final_audit_determination": {
            "second_audit",
            "conclusion",
        },
    }
    return str(project_status or "") in allowed.get(str(document_type), set())


def _has_project_identity(fields):
    return any(
        _field_value(field, "semantic_key")
        in {"project.code", "project.name", "party.owner", "party.contractor"}
        and _field_value(field, "normalized_value") not in (None, "")
        for field in fields
    )


def _first_money(values):
    for key in (
        "contract.amount_reference",
        "contract.amount",
        "audit.submitted_amount",
    ):
        value = values.get(key)
        if value not in (None, ""):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _project_amount_fen(value):
    try:
        return int(Decimal(str(value or 0)) * Decimal("100"))
    except (InvalidOperation, ValueError):
        return 0


def _normalize_code(value):
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", _text(value)).upper())


def _normalize_project_name(value):
    text = _normalize_text(value)
    for suffix in ("建设工程", "工程项目", "改造项目", "工程", "项目"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text


def _normalize_organization(value):
    return _normalize_text(value)


def _normalize_text(value):
    text = unicodedata.normalize("NFKC", _text(value)).lower()
    return re.sub(r"[\s\-—_·,，.。()（）]", "", text)


def _text(value):
    return str(value or "").strip()


def _field_value(field, name):
    return field.get(name) if isinstance(field, dict) else getattr(field, name, None)


def _candidate_conflict(code, project_id):
    messages = {
        "project_code_mismatch": "文件中的项目编号与候选项目不一致。",
        "both_parties_mismatch": "建设单位和施工单位均与候选项目不一致。",
        "amount_magnitude_conflict": "文件金额与候选项目金额相差一个数量级以上。",
    }
    return {
        **_blocker(code, "projectId", messages.get(code, "文件与候选项目存在冲突。")),
        "projectId": project_id,
    }


def _blocker(code, field, message):
    return {"code": code, "field": field, "message": message, "severity": "blocker"}


def _deduplicate_blockers(blockers):
    seen = set()
    result = []
    for blocker in blockers:
        key = (blocker["code"], blocker.get("projectId", ""))
        if key not in seen:
            seen.add(key)
            result.append(blocker)
    return result
