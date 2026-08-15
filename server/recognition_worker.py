"""Single-consumer SQLite worker for document recognition."""

from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.document_repository import (
    claim_next_recognition_job,
    create_review,
    mark_recognition_manual_required,
    RecognitionLeaseError,
    requeue_expired_recognition_jobs,
    save_recognition_result,
    schedule_recognition_retry,
)
from server.recognition.contracts import (
    RecognitionAdapterError,
    RecognitionPage,
    RecognitionRequest,
)
from server.recognition.normalizers import (
    materialize_schema_fields,
    normalize_extracted_fields,
)
from server.recognition.validators import build_review_blockers


LOGGER = logging.getLogger("server.recognition.worker")


class RecognitionPageQualityError(ValueError):
    pass


class RecognitionWorker:
    def __init__(
        self,
        *,
        connection_factory,
        adapter_resolver,
        request_loader=None,
        storage_root=None,
        storage=None,
        worker_id=None,
        poll_interval=1.0,
        lease_seconds=300,
        clock=None,
        quality_threshold=0.35,
    ):
        self.connection_factory = connection_factory
        self.adapter_resolver = adapter_resolver
        self.request_loader = request_loader or _storage_request_loader(
            storage or storage_root, quality_threshold=quality_threshold
        )
        self.worker_id = str(worker_id or f"recognition-worker-{uuid.uuid4().hex}")
        self.poll_interval = float(poll_interval)
        self.lease_seconds = int(lease_seconds)
        self.clock = clock or _now_iso
        self._stop = threading.Event()
        self._thread = None

    @property
    def is_alive(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        if self.is_alive:
            return
        self._stop.clear()
        self.recover_expired_jobs()
        self._thread = threading.Thread(
            target=self._run,
            name=self.worker_id,
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout=None):
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)
        return not self.is_alive

    def recover_expired_jobs(self, *, now=None):
        with self.connection_factory() as conn:
            return requeue_expired_recognition_jobs(conn, now=now)

    def run_once(self, *, now=None):
        claimed_at = now or self.clock()
        recognition_request = None
        load_error_code = ""
        with self.connection_factory() as conn:
            job = claim_next_recognition_job(
                conn,
                worker_id=self.worker_id,
                now=claimed_at,
                lease_seconds=self.lease_seconds,
            )
            if not job:
                return False
            try:
                recognition_request = self.request_loader(conn, job)
            except RecognitionPageQualityError:
                load_error_code = "ocr_page_quality_low"
            except Exception:
                load_error_code = "ocr_page_load_failed"

        if load_error_code:
            LOGGER.error(
                "Recognition page loading failed: code=%s job=%s",
                load_error_code,
                job["id"],
            )
            message = (
                "扫描件清晰度不足，请重新扫描或改为人工录入。"
                if load_error_code == "ocr_page_quality_low"
                else "识别页读取失败，请重新生成页面或改为人工录入。"
            )
            try:
                self._mark_manual(
                    job,
                    load_error_code,
                    message,
                    self.clock(),
                )
            except RecognitionLeaseError:
                self._log_lease_loss(job)
            return True

        try:
            try:
                result = self.adapter_resolver(job["adapter_key"]).recognize(
                    recognition_request
                )
                if result.status == "manual_required":
                    self._mark_manual(
                        job,
                        result.error_code or "ocr_manual_required",
                        "当前文档需要人工录入。",
                        self.clock(),
                    )
                    return True
                if result.status != "review_ready":
                    raise ValueError("unsupported recognition result status")
                normalized_fields = normalize_extracted_fields(
                    result.fields, job["schema_version"]
                )
                normalized_fields = materialize_schema_fields(
                    normalized_fields, job["schema_version"]
                )
                self._persist_success(job, result, normalized_fields, self.clock())
            except RecognitionAdapterError as exc:
                self._persist_adapter_failure(job, exc, self.clock())
            except (TypeError, ValueError, KeyError):
                LOGGER.error(
                    "Recognition result rejected: code=ocr_result_invalid job=%s",
                    job["id"],
                )
                self._mark_manual(
                    job,
                    "ocr_result_invalid",
                    "识别结果结构不符合当前文档模式。",
                    self.clock(),
                )
            except Exception:
                LOGGER.error(
                    "Recognition worker internal failure: code=ocr_internal_error job=%s",
                    job["id"],
                )
                self._mark_manual(
                    job,
                    "ocr_internal_error",
                    "识别任务发生内部错误，请人工处理。",
                    self.clock(),
                )
        except RecognitionLeaseError:
            self._log_lease_loss(job)
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                processed = self.run_once()
            except Exception:
                LOGGER.error("Recognition worker loop recovered from internal failure")
                processed = False
            if not processed:
                self._stop.wait(self.poll_interval)

    @staticmethod
    def _log_lease_loss(job):
        LOGGER.error(
            "Recognition result discarded after lease loss: job=%s", job["id"]
        )

    def _persist_success(self, job, result, normalized_fields, now):
        blocks = [
            {
                "page_id": block.page_id,
                "block_type": block.block_type,
                "raw_text": block.raw_text,
                "confidence": block.confidence,
                "bbox": block.bbox,
                "row_index": block.row_index,
                "column_index": block.column_index,
                "metadata": block.metadata or {},
            }
            for block in result.blocks
        ]
        fields = []
        for field in normalized_fields:
            fields.append(
                {
                    **field,
                    "anchors": [
                        {
                            "page_id": anchor.page_id,
                            "bbox": anchor.bbox,
                            "source_text": anchor.source_text,
                        }
                        for anchor in field["anchors"]
                    ],
                }
            )
        with self.connection_factory() as conn:
            source = conn.execute(
                """
                SELECT d.id AS document_id, d.document_type, d.project_id,
                       d.candidate_project_id
                FROM document_versions dv
                JOIN documents d ON d.id = dv.document_id
                WHERE dv.id = ?
                """,
                (job["document_version_id"],),
            ).fetchone()
            if not source:
                raise ValueError("recognition document is missing")
            save_recognition_result(
                conn,
                job_id=job["id"],
                worker_id=self.worker_id,
                model_version=result.model_version,
                provider_request_id=result.provider_request_id,
                blocks=blocks,
                fields=fields,
                now=now,
            )
            blockers = build_review_blockers(source["document_type"], fields)
            create_review(
                conn,
                document_id=source["document_id"],
                document_version_id=job["document_version_id"],
                recognition_job_id=job["id"],
                project_id=source["project_id"],
                candidate_project_id=source["candidate_project_id"],
                blockers=blockers,
                warnings=[],
                now=now,
            )

    def _persist_adapter_failure(self, job, exc, now):
        if not exc.retryable:
            self._mark_manual(job, exc.code, str(exc), now)
            return
        retry_at = _add_seconds(now, min(2 ** int(job["attempts"]), 300))
        with self.connection_factory() as conn:
            schedule_recognition_retry(
                conn,
                job_id=job["id"],
                worker_id=self.worker_id,
                error_code=exc.code,
                error_message=str(exc),
                retry_at=retry_at,
                now=now,
            )

    def _mark_manual(self, job, code, message, now):
        with self.connection_factory() as conn:
            mark_recognition_manual_required(
                conn,
                job_id=job["id"],
                worker_id=self.worker_id,
                error_code=code,
                error_message=message,
                now=now,
            )


def _storage_request_loader(storage, *, quality_threshold):
    file_storage = storage if hasattr(storage, "read_bytes") else None
    root = Path(storage).resolve() if storage and file_storage is None else None

    def load(conn, job):
        if root is None and file_storage is None:
            raise ValueError("recognition storage root is not configured")
        rows = conn.execute(
            """
            SELECT dp.*, d.document_type
            FROM document_pages dp
            JOIN document_versions dv ON dv.id = dp.document_version_id
            JOIN documents d ON d.id = dv.document_id
            WHERE dp.document_version_id = ?
            ORDER BY dp.page_number
            """,
            (job["document_version_id"],),
        ).fetchall()
        if not rows:
            raise ValueError("recognition document has no rendered pages")
        if any(
            row["quality_score"] is not None
            and float(row["quality_score"]) < float(quality_threshold)
            for row in rows
        ):
            raise RecognitionPageQualityError("recognition page quality is too low")
        pages = []
        for row in rows:
            if file_storage is not None:
                image_bytes = file_storage.read_bytes(row["relative_path"])
            else:
                path = _safe_storage_path(root, row["relative_path"])
                image_bytes = path.read_bytes()
            pages.append(
                RecognitionPage(
                    page_id=row["id"],
                    page_number=int(row["page_number"]),
                    image_bytes=image_bytes,
                    width_px=int(row["width_px"]),
                    height_px=int(row["height_px"]),
                )
            )
        return RecognitionRequest(
            job_id=job["id"],
            document_type=rows[0]["document_type"],
            schema_version=job["schema_version"],
            pages=tuple(pages),
        )

    return load


def _safe_storage_path(root, relative_path):
    relative = Path(str(relative_path).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("recognition page path escapes storage root")
    resolved = (root / relative).resolve()
    if os.path.commonpath((str(root), str(resolved))) != str(root):
        raise ValueError("recognition page path escapes storage root")
    return resolved


def _add_seconds(value, seconds):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (parsed + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
