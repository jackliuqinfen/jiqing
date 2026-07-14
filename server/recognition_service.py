"""Application services for durable recognition jobs."""

from server.document_repository import create_recognition_job


def enqueue_recognition(
    conn,
    *,
    document_version_id,
    adapter_key,
    schema_version,
    idempotency_key,
    max_attempts=3,
    now=None,
):
    return create_recognition_job(
        conn,
        document_version_id=document_version_id,
        adapter_key=adapter_key,
        schema_version=schema_version,
        idempotency_key=idempotency_key,
        max_attempts=max_attempts,
        now=now,
    )


def recognition_job_snapshot(conn, job_id):
    row = conn.execute(
        """
        SELECT rj.*,
               (SELECT COUNT(*) FROM ocr_blocks ob WHERE ob.recognition_job_id = rj.id) AS block_count,
               (SELECT COUNT(*) FROM extracted_fields ef WHERE ef.recognition_job_id = rj.id) AS field_count,
               COALESCE((
                 SELECT dr.status FROM document_reviews dr
                 WHERE dr.recognition_job_id = rj.id
                 ORDER BY dr.opened_at DESC LIMIT 1
               ), '') AS review_status,
               COALESCE((
                 SELECT dr.id FROM document_reviews dr
                 WHERE dr.recognition_job_id = rj.id
                 ORDER BY dr.opened_at DESC LIMIT 1
               ), '') AS review_id
        FROM recognition_jobs rj
        WHERE rj.id = ?
        """,
        (job_id,),
    ).fetchone()
    return dict(row) if row else None


def recognition_health_payload(conn, *, recognition_configured, worker_alive):
    counts = {
        "queued": 0,
        "running": 0,
        "review_ready": 0,
        "manual_required": 0,
        "failed": 0,
    }
    for row in conn.execute(
        "SELECT status, COUNT(*) AS count FROM recognition_jobs GROUP BY status"
    ).fetchall():
        counts[str(row["status"])] = int(row["count"])
    return {
        "recognitionConfigured": bool(recognition_configured),
        "recognitionWorkerAlive": bool(worker_alive),
        "recognitionQueue": counts,
    }
