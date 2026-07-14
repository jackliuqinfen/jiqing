"""Persistence primitives for the immutable document evidence graph."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone


class DocumentRepositoryError(RuntimeError):
    """Base repository error with no HTTP concerns."""


class DocumentNotFoundError(DocumentRepositoryError):
    pass


class RecognitionJobNotFoundError(DocumentRepositoryError):
    pass


class RecognitionIdempotencyConflictError(DocumentRepositoryError):
    pass


class RecognitionLeaseError(DocumentRepositoryError):
    pass


class EvidenceGraphMismatchError(DocumentRepositoryError):
    pass


class ReviewImmutableError(DocumentRepositoryError):
    pass


class InvalidEvidenceAnchorError(DocumentRepositoryError):
    pass


def create_document_upload(
    conn,
    *,
    document_type,
    lifecycle_stage,
    original_name,
    mime_type,
    file_size,
    sha256,
    relative_path,
    uploaded_by,
    project_id=None,
    candidate_project_id=None,
    document_id=None,
    now=None,
):
    """Create a document/version or replay the same scoped content upload."""
    now = now or _now_iso()
    if document_id:
        document = _fetch_one(conn, "SELECT * FROM documents WHERE id = ?", (document_id,))
        if not document:
            raise DocumentNotFoundError(document_id)
        existing = _fetch_one(
            conn,
            "SELECT * FROM document_versions WHERE document_id = ? AND sha256 = ?",
            (document_id, sha256),
        )
    else:
        existing = _fetch_one(
            conn,
            """
            SELECT dv.*
            FROM document_versions dv
            JOIN documents d ON d.id = dv.document_id
            WHERE d.document_type = ?
              AND d.lifecycle_stage = ?
              AND COALESCE(d.project_id, '') = COALESCE(?, '')
              AND COALESCE(d.candidate_project_id, '') = COALESCE(?, '')
              AND (
                    COALESCE(d.project_id, '') <> ''
                 OR COALESCE(d.candidate_project_id, '') <> ''
                 OR d.created_by = ?
              )
              AND dv.sha256 = ?
            ORDER BY dv.uploaded_at, dv.version_no
            LIMIT 1
            """,
            (
                document_type,
                lifecycle_stage,
                project_id,
                candidate_project_id,
                uploaded_by,
                sha256,
            ),
        )
        document = None

    if existing:
        existing_document = _fetch_one(
            conn, "SELECT * FROM documents WHERE id = ?", (existing["document_id"],)
        )
        return {
            "document": existing_document,
            "version": existing,
            "replayed": True,
            "cross_project_duplicate_count": 0,
        }

    cross_project_duplicate_count = int(
        conn.execute(
        """
        SELECT COUNT(*)
        FROM document_versions dv
        JOIN documents d ON d.id = dv.document_id
        WHERE dv.sha256 = ?
          AND COALESCE(d.project_id, '') <> COALESCE(?, '')
        """,
        (sha256, project_id),
        ).fetchone()[0]
    )

    if not document:
        document_id = document_id or uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO documents
            (id, document_type, lifecycle_stage, project_id, candidate_project_id,
             status, source, current_version_id, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'uploaded', 'user_upload', NULL, ?, ?, ?)
            """,
            (
                document_id,
                document_type,
                lifecycle_stage,
                project_id,
                candidate_project_id,
                uploaded_by,
                now,
                now,
            ),
        )
        version_no = 1
    else:
        version_no = int(
            conn.execute(
                "SELECT COALESCE(MAX(version_no), 0) + 1 FROM document_versions WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0]
        )

    replaced_version_id = document["current_version_id"] if document else None
    version_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO document_versions
        (id, document_id, version_no, original_name, mime_type, file_size, sha256,
         relative_path, replaced_version_id, uploaded_by, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            document_id,
            version_no,
            original_name,
            mime_type,
            int(file_size),
            sha256,
            relative_path,
            replaced_version_id,
            uploaded_by,
            now,
        ),
    )
    conn.execute(
        "UPDATE documents SET current_version_id = ?, status = 'uploaded', updated_at = ? WHERE id = ?",
        (version_id, now, document_id),
    )
    return {
        "document": _fetch_one(conn, "SELECT * FROM documents WHERE id = ?", (document_id,)),
        "version": _fetch_one(
            conn, "SELECT * FROM document_versions WHERE id = ?", (version_id,)
        ),
        "replayed": False,
        "cross_project_duplicate_count": cross_project_duplicate_count,
    }


def add_document_pages(conn, *, document_version_id, pages, now=None):
    now = now or _now_iso()
    saved = []
    for page in sorted(pages, key=lambda item: int(item["page_number"])):
        page_id = page.get("id") or uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO document_pages
            (id, document_version_id, page_number, relative_path, width_px, height_px,
             dpi, rotation_degrees, quality_score, preprocessing_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                page_id,
                document_version_id,
                int(page["page_number"]),
                page["relative_path"],
                int(page["width_px"]),
                int(page["height_px"]),
                int(page.get("dpi", 300)),
                int(page.get("rotation_degrees", 0)),
                page.get("quality_score"),
                page["preprocessing_version"],
                now,
            ),
        )
        saved.append(_fetch_one(conn, "SELECT * FROM document_pages WHERE id = ?", (page_id,)))
    return saved


def create_recognition_job(
    conn,
    *,
    document_version_id,
    adapter_key,
    schema_version,
    idempotency_key,
    max_attempts=3,
    now=None,
):
    existing = _fetch_one(
        conn, "SELECT * FROM recognition_jobs WHERE idempotency_key = ?", (idempotency_key,)
    )
    if existing:
        if (
            existing["document_version_id"] != document_version_id
            or existing["adapter_key"] != adapter_key
            or existing["schema_version"] != schema_version
        ):
            raise RecognitionIdempotencyConflictError(
                "recognition idempotency key belongs to another request"
            )
        return existing
    now = now or _now_iso()
    job_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO recognition_jobs
        (id, document_version_id, status, adapter_key, schema_version,
         idempotency_key, max_attempts, created_at, updated_at)
        VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            document_version_id,
            adapter_key,
            schema_version,
            idempotency_key,
            int(max_attempts),
            now,
            now,
        ),
    )
    _update_document_status_for_version(conn, document_version_id, "recognition_queued", now)
    return _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))


def claim_next_recognition_job(conn, *, worker_id, now=None, lease_seconds=120):
    """Atomically lease the oldest runnable job; this function owns its transaction."""
    now = now or _now_iso()
    lease_expires_at = _add_seconds(now, lease_seconds)
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = _fetch_one(
            conn,
            """
            SELECT * FROM recognition_jobs
            WHERE attempts < max_attempts
              AND (
                (
                  status IN ('queued', 'failed')
                  AND (next_attempt_at = '' OR next_attempt_at <= ?)
                )
                OR (status = 'running' AND lease_expires_at <> '' AND lease_expires_at <= ?)
              )
            ORDER BY created_at, id
            LIMIT 1
            """,
            (now, now),
        )
        if not job:
            conn.commit()
            return None
        conn.execute(
            """
            UPDATE recognition_jobs
            SET status = 'running', attempts = attempts + 1, lease_owner = ?,
                lease_expires_at = ?, started_at = CASE WHEN started_at = '' THEN ? ELSE started_at END,
                next_attempt_at = '', finished_at = '', error_code = '', error_message = '', updated_at = ?
            WHERE id = ?
            """,
            (worker_id, lease_expires_at, now, now, job["id"]),
        )
        claimed = _fetch_one(
            conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job["id"],)
        )
        _update_document_status_for_version(
            conn, claimed["document_version_id"], "recognizing", now
        )
        conn.commit()
        return claimed
    except Exception:
        conn.rollback()
        raise


def mark_recognition_failed(
    conn, *, job_id, worker_id, error_code, error_message, now=None
):
    now = now or _now_iso()
    job = _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))
    if not job:
        raise RecognitionJobNotFoundError(job_id)
    _assert_job_lease(job, worker_id, now)
    conn.execute(
        """
        UPDATE recognition_jobs
        SET status = 'failed', error_code = ?, error_message = ?, lease_owner = '',
            lease_expires_at = '', finished_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (error_code, error_message, now, now, job_id),
    )
    _update_document_status_for_version(conn, job["document_version_id"], "failed", now)
    return _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))


def schedule_recognition_retry(
    conn,
    *,
    job_id,
    worker_id,
    error_code,
    error_message,
    retry_at,
    now=None,
):
    now = now or _now_iso()
    job = _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))
    if not job:
        raise RecognitionJobNotFoundError(job_id)
    _assert_job_lease(job, worker_id, now)
    if int(job["attempts"]) >= int(job["max_attempts"]):
        return mark_recognition_manual_required(
            conn,
            job_id=job_id,
            worker_id=worker_id,
            error_code=error_code,
            error_message=error_message,
            now=now,
        )
    conn.execute(
        """
        UPDATE recognition_jobs
        SET status = 'queued', error_code = ?, error_message = ?, lease_owner = '',
            lease_expires_at = '', next_attempt_at = ?, finished_at = '', updated_at = ?
        WHERE id = ?
        """,
        (error_code, error_message, retry_at, now, job_id),
    )
    _update_document_status_for_version(
        conn, job["document_version_id"], "recognition_queued", now
    )
    return _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))


def mark_recognition_manual_required(
    conn, *, job_id, worker_id, error_code, error_message, now=None
):
    now = now or _now_iso()
    job = _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))
    if not job:
        raise RecognitionJobNotFoundError(job_id)
    _assert_job_lease(job, worker_id, now)
    conn.execute(
        """
        UPDATE recognition_jobs
        SET status = 'manual_required', error_code = ?, error_message = ?,
            lease_owner = '', lease_expires_at = '', next_attempt_at = '',
            finished_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (error_code, error_message, now, now, job_id),
    )
    _update_document_status_for_version(
        conn, job["document_version_id"], "manual_required", now
    )
    return _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))


def requeue_expired_recognition_jobs(conn, *, now=None):
    now = now or _now_iso()
    expired = _fetch_all(
        conn,
        """
        SELECT * FROM recognition_jobs
        WHERE status = 'running' AND lease_expires_at <> '' AND lease_expires_at <= ?
        """,
        (now,),
    )
    for job in expired:
        target_status = (
            "manual_required"
            if int(job["attempts"]) >= int(job["max_attempts"])
            else "queued"
        )
        conn.execute(
            """
            UPDATE recognition_jobs
            SET status = ?, lease_owner = '', lease_expires_at = '',
                next_attempt_at = '', error_code = 'recognition_lease_expired',
                error_message = '识别任务租约已过期。', updated_at = ?
            WHERE id = ?
            """,
            (target_status, now, job["id"]),
        )
        document_status = (
            "manual_required"
            if target_status == "manual_required"
            else "recognition_queued"
        )
        _update_document_status_for_version(
            conn, job["document_version_id"], document_status, now
        )
    return len(expired)


def save_recognition_result(
    conn,
    *,
    job_id,
    worker_id,
    model_version,
    provider_request_id,
    blocks,
    fields,
    now=None,
):
    now = now or _now_iso()
    job = _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))
    if not job:
        raise RecognitionJobNotFoundError(job_id)
    _assert_job_lease(job, worker_id, now)
    page_ids = {
        row["id"]
        for row in _fetch_all(
            conn,
            "SELECT id FROM document_pages WHERE document_version_id = ?",
            (job["document_version_id"],),
        )
    }
    for block in blocks:
        if block["page_id"] not in page_ids:
            raise EvidenceGraphMismatchError("OCR block page belongs to another version")
        _validate_bbox(block["bbox"])
    for field in fields:
        for anchor in field.get("anchors", []):
            if anchor["page_id"] not in page_ids:
                raise EvidenceGraphMismatchError(
                    "evidence anchor page belongs to another version"
                )
            _validate_bbox(anchor["bbox"])
    for block in blocks:
        conn.execute(
            """
            INSERT INTO ocr_blocks
            (id, recognition_job_id, document_page_id, block_type, raw_text,
             confidence, bbox_json, row_index, column_index, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block.get("id") or uuid.uuid4().hex,
                job_id,
                block["page_id"],
                block["block_type"],
                block.get("raw_text", ""),
                block.get("confidence"),
                _json(block["bbox"]),
                block.get("row_index"),
                block.get("column_index"),
                _json(block.get("metadata", {})),
                now,
            ),
        )
    for field in fields:
        field_id = field.get("id") or uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO extracted_fields
            (id, recognition_job_id, semantic_key, raw_value, normalized_value_json,
             confidence, validation_status, source_kind, model_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                field_id,
                job_id,
                field["semantic_key"],
                field.get("raw_value", ""),
                _json(field.get("normalized_value")),
                field.get("confidence"),
                field.get("validation_status", "unvalidated"),
                field.get("source_kind", "ocr"),
                model_version,
                now,
            ),
        )
        for anchor in field.get("anchors", []):
            conn.execute(
                """
                INSERT INTO evidence_anchors
                (id, extracted_field_id, document_version_id, document_page_id,
                 bbox_json, source_text, image_crop_relative_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    anchor.get("id") or uuid.uuid4().hex,
                    field_id,
                    job["document_version_id"],
                    anchor["page_id"],
                    _json(anchor["bbox"]),
                    anchor.get("source_text", ""),
                    anchor.get("image_crop_relative_path", ""),
                    now,
                ),
            )
    conn.execute(
        """
        UPDATE recognition_jobs
        SET status = 'review_ready', model_version = ?, provider_request_id = ?,
            provider_metadata_json = '{}', lease_owner = '', lease_expires_at = '',
            finished_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (model_version, provider_request_id, now, now, job_id),
    )
    _update_document_status_for_version(conn, job["document_version_id"], "review_ready", now)
    return _fetch_one(conn, "SELECT * FROM recognition_jobs WHERE id = ?", (job_id,))


def create_review(
    conn,
    *,
    document_id,
    document_version_id,
    recognition_job_id,
    project_id=None,
    candidate_project_id=None,
    blockers=None,
    warnings=None,
    now=None,
):
    document = _fetch_one(conn, "SELECT * FROM documents WHERE id = ?", (document_id,))
    version = _fetch_one(
        conn, "SELECT * FROM document_versions WHERE id = ?", (document_version_id,)
    )
    job = _fetch_one(
        conn, "SELECT * FROM recognition_jobs WHERE id = ?", (recognition_job_id,)
    )
    if not document or not version or not job:
        raise DocumentNotFoundError("document review source is missing")
    if version["document_id"] != document_id or job["document_version_id"] != document_version_id:
        raise EvidenceGraphMismatchError("review document, version, and job must match")
    if document["current_version_id"] != document_version_id:
        raise EvidenceGraphMismatchError("only the current document version can be reviewed")
    if job["status"] != "review_ready":
        raise EvidenceGraphMismatchError("recognition job is not ready for review")
    if document["project_id"] and project_id != document["project_id"]:
        raise EvidenceGraphMismatchError("review project does not match document project")
    existing = _fetch_one(
        conn,
        "SELECT * FROM document_reviews WHERE document_version_id = ? AND recognition_job_id = ?",
        (document_version_id, recognition_job_id),
    )
    if existing:
        return existing
    now = now or _now_iso()
    review_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO document_reviews
        (id, document_id, document_version_id, recognition_job_id, project_id,
         candidate_project_id, status, review_version, blockers_json, warnings_json,
         opened_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'open', 0, ?, ?, ?, ?)
        """,
        (
            review_id,
            document_id,
            document_version_id,
            recognition_job_id,
            project_id,
            candidate_project_id,
            _json(blockers or []),
            _json(warnings or []),
            now,
            now,
        ),
    )
    conn.execute(
        "UPDATE documents SET status = 'in_review', updated_at = ? WHERE id = ?",
        (now, document_id),
    )
    return _fetch_one(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))


def upsert_review_decision(
    conn,
    *,
    review_id,
    extracted_field_id,
    decision,
    ai_value,
    confirmed_value,
    reviewer_id,
    reviewer_name,
    reason="",
    now=None,
):
    now = now or _now_iso()
    review = _require_mutable_review(conn, review_id)
    field = _fetch_one(
        conn, "SELECT * FROM extracted_fields WHERE id = ?", (extracted_field_id,)
    )
    if not field or field["recognition_job_id"] != review["recognition_job_id"]:
        raise EvidenceGraphMismatchError("review decision field belongs to another job")
    existing = _fetch_one(
        conn,
        "SELECT * FROM review_decisions WHERE review_id = ? AND extracted_field_id = ?",
        (review_id, extracted_field_id),
    )
    if existing:
        revision_no = int(
            conn.execute(
                "SELECT COALESCE(MAX(revision_no), 0) + 1 FROM review_decision_history WHERE review_decision_id = ?",
                (existing["id"],),
            ).fetchone()[0]
        )
        conn.execute(
            """
            INSERT INTO review_decision_history
            (id, review_decision_id, review_id, extracted_field_id, decision,
             ai_value_json, confirmed_value_json, reason, reviewer_id, reviewer_name,
             revision_no, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                existing["id"],
                review_id,
                extracted_field_id,
                existing["decision"],
                existing["ai_value_json"],
                existing["confirmed_value_json"],
                existing["reason"],
                existing["reviewer_id"],
                existing["reviewer_name"],
                revision_no,
                now,
            ),
        )
        decision_id = existing["id"]
        conn.execute(
            """
            UPDATE review_decisions
            SET decision = ?, ai_value_json = ?, confirmed_value_json = ?, reason = ?,
                reviewer_id = ?, reviewer_name = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                decision,
                _json(ai_value),
                _json(confirmed_value),
                reason,
                reviewer_id,
                reviewer_name,
                now,
                decision_id,
            ),
        )
    else:
        decision_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO review_decisions
            (id, review_id, extracted_field_id, decision, ai_value_json,
             confirmed_value_json, reason, reviewer_id, reviewer_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                review_id,
                extracted_field_id,
                decision,
                _json(ai_value),
                _json(confirmed_value),
                reason,
                reviewer_id,
                reviewer_name,
                now,
                now,
            ),
        )
    conn.execute(
        """
        UPDATE document_reviews
        SET status = 'in_review', review_version = review_version + 1,
            reviewer_id = ?, reviewer_name = ?, updated_at = ?
        WHERE id = ? AND review_version = ?
        """,
        (reviewer_id, reviewer_name, now, review_id, review["review_version"]),
    )
    return _fetch_one(conn, "SELECT * FROM review_decisions WHERE id = ?", (decision_id,))


def review_snapshot(conn, review_id):
    review = _fetch_one(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
    if not review:
        raise DocumentNotFoundError(review_id)
    review["fields"] = _fetch_all(
        conn,
        "SELECT * FROM extracted_fields WHERE recognition_job_id = ? ORDER BY semantic_key",
        (review["recognition_job_id"],),
    )
    review["decisions"] = _fetch_all(
        conn,
        "SELECT * FROM review_decisions WHERE review_id = ? ORDER BY created_at, id",
        (review_id,),
    )
    review["anchors"] = _fetch_all(
        conn,
        """
        SELECT ea.* FROM evidence_anchors ea
        JOIN extracted_fields ef ON ef.id = ea.extracted_field_id
        WHERE ef.recognition_job_id = ?
        ORDER BY ea.document_page_id, ea.id
        """,
        (review["recognition_job_id"],),
    )
    return review


def mark_review_confirmed(
    conn,
    *,
    review_id,
    idempotency_key,
    project_id,
    stage_key,
    form_template_version,
    extraction_schema_version,
    values,
    evidence_manifest,
    reviewer_id,
    reviewer_name,
    now=None,
):
    now = now or _now_iso()
    review = _fetch_one(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
    if not review:
        raise DocumentNotFoundError(review_id)
    if review["status"] == "confirmed":
        if review["confirmation_idempotency_key"] != idempotency_key:
            raise ReviewImmutableError("confirmed review cannot be changed")
        return _fetch_one(
            conn, "SELECT * FROM stage_form_snapshots WHERE review_id = ?", (review_id,)
        )

    document = _fetch_one(
        conn, "SELECT * FROM documents WHERE id = ?", (review["document_id"],)
    )
    if not document or document["current_version_id"] != review["document_version_id"]:
        raise EvidenceGraphMismatchError(
            "review document version is no longer current"
        )

    if review["project_id"] and review["project_id"] != project_id:
        raise EvidenceGraphMismatchError("snapshot project does not match review project")
    anchor_ids = {
        str(anchor_id)
        for values_for_field in evidence_manifest.values()
        for anchor_id in values_for_field
    }
    if anchor_ids:
        placeholders = ",".join("?" for _ in anchor_ids)
        rows = _fetch_all(
            conn,
            f"""
            SELECT ea.id, ef.semantic_key
            FROM evidence_anchors ea
            JOIN extracted_fields ef ON ef.id = ea.extracted_field_id
            WHERE ef.recognition_job_id = ? AND ea.id IN ({placeholders})
            """,
            (review["recognition_job_id"], *sorted(anchor_ids)),
        )
        anchors_by_id = {row["id"]: row["semantic_key"] for row in rows}
        if set(anchors_by_id) != anchor_ids:
            raise EvidenceGraphMismatchError("snapshot references unknown evidence anchors")
        for semantic_key, semantic_anchor_ids in evidence_manifest.items():
            if any(anchors_by_id[str(anchor_id)] != semantic_key for anchor_id in semantic_anchor_ids):
                raise EvidenceGraphMismatchError(
                    "snapshot evidence anchor belongs to another semantic field"
                )

    existing_key = _fetch_one(
        conn,
        "SELECT * FROM stage_form_snapshots WHERE review_id = ?",
        (review_id,),
    )
    if existing_key:
        raise ReviewImmutableError("review snapshot already exists")

    snapshot_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO stage_form_snapshots
        (id, review_id, project_id, stage_key, document_version_id,
         form_template_version, extraction_schema_version, values_json,
         evidence_manifest_json, confirmed_by, confirmed_by_name, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            review_id,
            project_id,
            stage_key,
            review["document_version_id"],
            form_template_version,
            extraction_schema_version,
            _json(values),
            _json(evidence_manifest),
            reviewer_id,
            reviewer_name,
            now,
        ),
    )
    conn.execute(
        """
        UPDATE document_reviews
        SET status = 'confirmed', confirmation_idempotency_key = ?, reviewer_id = ?,
            reviewer_name = ?, confirmed_at = ?, updated_at = ?,
            review_version = review_version + 1
        WHERE id = ?
        """,
        (idempotency_key, reviewer_id, reviewer_name, now, now, review_id),
    )
    conn.execute(
        "UPDATE documents SET status = 'confirmed', project_id = ?, updated_at = ? WHERE id = ?",
        (project_id, now, review["document_id"]),
    )
    return _fetch_one(
        conn, "SELECT * FROM stage_form_snapshots WHERE id = ?", (snapshot_id,)
    )


def _require_mutable_review(conn, review_id):
    review = _fetch_one(conn, "SELECT * FROM document_reviews WHERE id = ?", (review_id,))
    if not review:
        raise DocumentNotFoundError(review_id)
    if review["status"] == "confirmed":
        raise ReviewImmutableError("confirmed review cannot be changed")
    return review


def _update_document_status_for_version(conn, document_version_id, status, now):
    conn.execute(
        """
        UPDATE documents
        SET status = ?, updated_at = ?
        WHERE id = (SELECT document_id FROM document_versions WHERE id = ?)
          AND current_version_id = ?
        """,
        (status, now, document_version_id, document_version_id),
    )


def _assert_job_lease(job, worker_id, now):
    if job["status"] != "running" or job["lease_owner"] != worker_id:
        raise RecognitionLeaseError("recognition job is not leased by this worker")
    expires_at = job.get("lease_expires_at") or ""
    if not expires_at or expires_at < now:
        raise RecognitionLeaseError("recognition job lease has expired")


def _validate_bbox(bbox):
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise InvalidEvidenceAnchorError("bbox must be [x, y, width, height]")
    x, y, width, height = (float(value) for value in bbox)
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > 1.000001
        or y + height > 1.000001
    ):
        raise InvalidEvidenceAnchorError("bbox coordinates must be normalized")


def _fetch_one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def _fetch_all(conn, sql, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _add_seconds(value, seconds):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
