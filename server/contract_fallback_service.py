"""Safe manual and external-AI fallbacks for contract document review."""

from __future__ import annotations

import json
import math
import re

from server import document_repository
from server.recognition.normalizers import (
    materialize_schema_fields,
    normalize_extracted_fields,
)
from server.recognition.schemas import schema_for_version
from server.recognition_service import recognition_job_snapshot


MAX_EXTERNAL_MARKDOWN_SIZE = 128 * 1024
ALLOWED_FALLBACK_ADAPTERS = frozenset({"manual-entry", "external-ai-paste"})
_JSON_BLOCK = re.compile(r"```json\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


class ContractFallbackError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = str(code)


def parse_external_contract_markdown(markdown):
    text = str(markdown or "")
    if len(text.encode("utf-8")) > MAX_EXTERNAL_MARKDOWN_SIZE:
        raise ContractFallbackError("external_markdown_too_large", "外部 AI 结果过长，请精简后重试。")
    blocks = _JSON_BLOCK.findall(text)
    if len(blocks) != 1:
        raise ContractFallbackError(
            "external_json_block_count_invalid",
            "外部 AI 结果只能包含一个 json 代码块。",
        )
    try:
        payload = json.loads(
            blocks[0],
            object_pairs_hook=_strict_json_object,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise ContractFallbackError(
            "external_json_invalid", "外部 AI 返回的 JSON 无法解析。"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {"schemaVersion", "fields"}:
        raise ContractFallbackError(
            "external_payload_invalid", "外部 AI 结果必须包含 schemaVersion 和 fields。"
        )
    if payload["schemaVersion"] != "contract.v1":
        raise ContractFallbackError(
            "external_schema_version_invalid", "外部 AI 结果版本必须为 contract.v1。"
        )
    field_payload = payload["fields"]
    if not isinstance(field_payload, dict):
        raise ContractFallbackError("external_fields_invalid", "外部 AI 字段必须是 JSON 对象。")

    schema = schema_for_version("contract.v1")
    if len(field_payload) > len(schema.semantic_keys):
        raise ContractFallbackError("external_field_count_invalid", "外部 AI 字段数量超过合同模式限制。")
    fields = []
    for semantic_key, item in field_payload.items():
        if semantic_key not in schema.semantic_keys:
            raise ContractFallbackError(
                "external_semantic_key_invalid", f"不支持的合同字段：{semantic_key}。"
            )
        if not isinstance(item, dict) or not set(item).issubset({"value", "evidence", "page"}):
            raise ContractFallbackError(
                "external_field_invalid", f"合同字段 {semantic_key} 的结构无效。"
            )
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ContractFallbackError(
                "external_field_value_invalid", f"合同字段 {semantic_key} 的值类型无效。"
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise ContractFallbackError(
                "external_field_value_invalid", f"合同字段 {semantic_key} 包含非法数字。"
            )
        raw_value = str(value).strip()
        if not raw_value:
            continue
        evidence = item.get("evidence", "")
        if not isinstance(evidence, str) or len(evidence) > 4000:
            raise ContractFallbackError(
                "external_evidence_invalid", f"合同字段 {semantic_key} 的原文提示无效。"
            )
        page = item.get("page")
        if page is not None and (isinstance(page, bool) or not isinstance(page, int) or page <= 0):
            raise ContractFallbackError(
                "external_page_invalid", f"合同字段 {semantic_key} 的页码无效。"
            )
        fields.append(
            {
                "semantic_key": semantic_key,
                "raw_value": raw_value,
                "confidence": None,
                "anchors": (),
                "source_kind": "external_ai",
                "external_evidence": evidence.strip(),
                "external_page": page,
            }
        )
    return fields


def manual_contract_fields(values):
    if values is None:
        return []
    if not isinstance(values, dict):
        raise ContractFallbackError("manual_fields_invalid", "手工合同字段必须是对象。")
    schema = schema_for_version("contract.v1")
    fields = []
    for semantic_key, value in values.items():
        if semantic_key not in schema.semantic_keys:
            raise ContractFallbackError(
                "manual_semantic_key_invalid", f"不支持的合同字段：{semantic_key}。"
            )
        if value is None or value == "":
            continue
        if isinstance(value, list):
            raw_value = "\n".join(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ContractFallbackError(
                "manual_field_value_invalid", f"合同字段 {semantic_key} 的值类型无效。"
            )
        else:
            raw_value = str(value).strip()
        if raw_value:
            fields.append(
                {
                    "semantic_key": semantic_key,
                    "raw_value": raw_value,
                    "confidence": None,
                    "anchors": (),
                    "source_kind": "manual",
                }
            )
    return fields


def create_fallback_review(
    conn,
    *,
    source_job_id,
    adapter_key,
    idempotency_key,
    fields,
    actor,
    fallback_reason,
    fallback_note="",
    now=None,
):
    _validate_fallback_request(adapter_key, idempotency_key, fallback_reason)
    source = document_repository._fetch_one(
        conn,
        """
        SELECT rj.*, dv.document_id
        FROM recognition_jobs rj
        JOIN document_versions dv ON dv.id = rj.document_version_id
        WHERE rj.id = ?
        """,
        (str(source_job_id or ""),),
    )
    if not source:
        raise ContractFallbackError("source_job_not_found", "未找到原识别任务。")
    if source["status"] not in {"failed", "manual_required"}:
        raise ContractFallbackError("fallback_status_invalid", "当前识别状态不能转入人工复核。")
    if source["schema_version"] != "contract.v1":
        raise ContractFallbackError("fallback_schema_invalid", "一期仅支持合同人工复核。")

    return _create_review_for_version(
        conn,
        document_id=source["document_id"],
        document_version_id=source["document_version_id"],
        source_job_id=source["id"],
        adapter_key=adapter_key,
        idempotency_key=idempotency_key,
        fields=fields,
        actor=actor,
        fallback_reason=fallback_reason,
        fallback_note=fallback_note,
        now=now,
    )


def create_direct_fallback_review(
    conn,
    *,
    document_version_id,
    adapter_key,
    idempotency_key,
    fields,
    actor,
    fallback_reason,
    fallback_note="",
    now=None,
):
    _validate_fallback_request(adapter_key, idempotency_key, fallback_reason)
    source = document_repository._fetch_one(
        conn,
        """
        SELECT dv.id AS document_version_id, dv.document_id, d.document_type
        FROM document_versions dv
        JOIN documents d ON d.id = dv.document_id
        WHERE dv.id = ?
        """,
        (str(document_version_id or ""),),
    )
    if not source:
        raise ContractFallbackError("document_version_not_found", "未找到合同文档版本。")
    if source["document_type"] != "construction_contract":
        raise ContractFallbackError("fallback_schema_invalid", "一期仅支持合同人工复核。")
    return _create_review_for_version(
        conn,
        document_id=source["document_id"],
        document_version_id=source["document_version_id"],
        source_job_id=None,
        adapter_key=adapter_key,
        idempotency_key=idempotency_key,
        fields=fields,
        actor=actor,
        fallback_reason=fallback_reason,
        fallback_note=fallback_note,
        now=now,
    )


def _validate_fallback_request(adapter_key, idempotency_key, fallback_reason):
    if adapter_key not in ALLOWED_FALLBACK_ADAPTERS:
        raise ContractFallbackError("fallback_adapter_invalid", "当前人工复核方式不受支持。")
    if not str(idempotency_key or "").strip():
        raise ContractFallbackError("fallback_idempotency_required", "人工复核必须提供幂等键。")
    if not str(fallback_reason or "").strip():
        raise ContractFallbackError("fallback_reason_required", "请选择转入人工复核的原因。")


def _strict_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractFallbackError("external_json_duplicate_key", f"外部 AI JSON 包含重复字段：{key}。")
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ContractFallbackError("external_json_non_finite", f"外部 AI JSON 包含非法数字：{value}。")


def _create_review_for_version(
    conn,
    *,
    document_id,
    document_version_id,
    source_job_id,
    adapter_key,
    idempotency_key,
    fields,
    actor,
    fallback_reason,
    fallback_note,
    now,
):

    job = document_repository.create_recognition_job(
        conn,
        document_version_id=document_version_id,
        adapter_key=adapter_key,
        schema_version="contract.v1",
        idempotency_key=str(idempotency_key).strip(),
        max_attempts=1,
        now=now,
    )
    existing_reason = str(job.get("fallback_reason") or "")
    existing_note = str(job.get("fallback_note") or "")
    if (existing_reason and existing_reason != str(fallback_reason).strip()) or (
        existing_note and existing_note != str(fallback_note or "").strip()
    ):
        raise ContractFallbackError(
            "fallback_idempotency_conflict", "人工复核幂等键已用于其他降级原因。"
        )
    existing_source_id = job.get("source_recognition_job_id")
    if existing_source_id and existing_source_id != source_job_id:
        raise ContractFallbackError(
            "fallback_idempotency_conflict", "人工复核幂等键已用于其他识别任务。"
        )
    if source_job_id:
        document_repository.link_fallback_job_source(
            conn,
            job_id=job["id"],
            source_recognition_job_id=source_job_id,
            now=now,
        )
    job = document_repository.record_fallback_provenance(
        conn,
        job_id=job["id"],
        fallback_reason=str(fallback_reason).strip(),
        fallback_note=str(fallback_note or "").strip(),
        now=now,
    )
    if not job or job.get("fallback_reason") != str(fallback_reason).strip():
        raise ContractFallbackError(
            "fallback_idempotency_conflict", "人工复核幂等键已用于其他降级原因。"
        )
    if job["status"] != "review_ready":
        normalized = normalize_extracted_fields(fields or [], "contract.v1")
        normalized = materialize_schema_fields(normalized, "contract.v1")
        document_repository.save_fallback_recognition_result(
            conn,
            job_id=job["id"],
            fields=normalized,
            model_version=f"{adapter_key}-v1",
            now=now,
        )
    review = document_repository.create_review(
        conn,
        document_id=document_id,
        document_version_id=document_version_id,
        recognition_job_id=job["id"],
        now=now,
    )
    snapshot = recognition_job_snapshot(conn, job["id"])
    snapshot["actor_id"] = str((actor or {}).get("id") or "")
    snapshot["review_id"] = review["id"]
    return snapshot
