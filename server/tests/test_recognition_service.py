import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

from server.document_repository import (
    add_document_pages,
    claim_next_recognition_job,
    create_document_upload,
)
from server.migrations import apply_pending_migrations
from server.recognition.contracts import (
    RecognitionAdapterError,
    RecognitionPage,
    RecognitionRequest,
    RecognitionResult,
    RecognizedAnchor,
    RecognizedField,
)
from server.recognition_service import (
    enqueue_recognition,
    recognition_health_payload,
    recognition_job_snapshot,
)
from server.recognition.schemas import schema_for_version
from server.recognition_worker import RecognitionWorker


NOW = "2026-07-13T01:00:00Z"


class _StaticAdapter:
    def recognize(self, request):
        return RecognitionResult(
            status="review_ready",
            provider_request_id="provider-1",
            adapter_key="test-http",
            model_version="model-1",
            blocks=(),
            fields=(
                RecognizedField(
                    semantic_key="project.name",
                    raw_value="测试工程",
                    normalized_value="provider-value-is-not-trusted",
                    confidence=0.9,
                    anchors=(
                        RecognizedAnchor(
                            page_id=request.pages[0].page_id,
                            bbox=(0.1, 0.1, 0.5, 0.1),
                            source_text="测试工程",
                        ),
                    ),
                ),
            ),
        )


class _RetryingAdapter:
    def recognize(self, _request):
        raise RecognitionAdapterError(
            "ocr_provider_timeout", retryable=True, message="识别服务请求超时。"
        )


class _MalformedAdapter:
    def recognize(self, request):
        return RecognitionResult(
            status="review_ready",
            provider_request_id="provider-bad",
            adapter_key="test-http",
            model_version="model-bad",
            blocks=(),
            fields=(
                RecognizedField(
                    semantic_key="provider.unknown_key",
                    raw_value="不能进入内部字段",
                    normalized_value="不能进入内部字段",
                    confidence=0.9,
                    anchors=(
                        RecognizedAnchor(
                            page_id=request.pages[0].page_id,
                            bbox=(0.1, 0.1, 0.5, 0.1),
                            source_text="不能进入内部字段",
                        ),
                    ),
                ),
            ),
        )


class _BlockingAdapter(_StaticAdapter):
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def recognize(self, request):
        self.entered.set()
        self.release.wait(timeout=3)
        return super().recognize(request)


class RecognitionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "recognition.sqlite3"
        with self.connection_factory() as conn:
            conn.execute(
                """
                CREATE TABLE project_records (
                  id TEXT PRIMARY KEY,
                  project_status TEXT DEFAULT 'awarded',
                  lifecycle_version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("INSERT INTO project_records (id) VALUES ('project-1')")
            conn.commit()
            apply_pending_migrations(conn)
            created = create_document_upload(
                conn,
                document_type="construction_contract",
                lifecycle_stage="contract_handoff",
                project_id="project-1",
                original_name="合同.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="hash-1",
                relative_path="documents/document-1/v1/original/contract.pdf",
                uploaded_by="user-1",
                now=NOW,
            )
            self.document_id = created["document"]["id"]
            self.version_id = created["version"]["id"]
            pages = add_document_pages(
                conn,
                document_version_id=self.version_id,
                pages=[
                    {
                        "page_number": 1,
                        "relative_path": "documents/document-1/v1/pages/page-0001.png",
                        "width_px": 1000,
                        "height_px": 2000,
                        "dpi": 300,
                        "rotation_degrees": 0,
                        "quality_score": 0.8,
                        "preprocessing_version": "scan-v1",
                    }
                ],
                now=NOW,
            )
            self.page_id = pages[0]["id"]
            conn.commit()

    def tearDown(self):
        self.temp.cleanup()

    @contextmanager
    def connection_factory(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def request_loader(self, _conn, job):
        return RecognitionRequest(
            job_id=job["id"],
            document_type="construction_contract",
            schema_version=job["schema_version"],
            pages=(
                RecognitionPage(
                    page_id=self.page_id,
                    page_number=1,
                    image_bytes=b"page-bytes",
                    width_px=1000,
                    height_px=2000,
                ),
            ),
        )

    def enqueue(self, *, idempotency_key="recognize-1", max_attempts=3):
        with self.connection_factory() as conn:
            return enqueue_recognition(
                conn,
                document_version_id=self.version_id,
                adapter_key="test-http",
                schema_version="contract.v1",
                idempotency_key=idempotency_key,
                max_attempts=max_attempts,
                now=NOW,
            )

    def worker(self, adapter, **overrides):
        options = {
            "connection_factory": self.connection_factory,
            "adapter_resolver": lambda _key: adapter,
            "request_loader": self.request_loader,
            "worker_id": "worker-1",
            "poll_interval": 0.01,
            "lease_seconds": 30,
            "clock": lambda: NOW,
        }
        options.update(overrides)
        return RecognitionWorker(**options)

    def test_recognition_reaches_review_ready_without_writing_business_facts(self):
        job = self.enqueue()

        self.assertTrue(self.worker(_StaticAdapter()).run_once(now=NOW))

        with self.connection_factory() as conn:
            snapshot = recognition_job_snapshot(conn, job["id"])
            self.assertEqual(snapshot["status"], "review_ready")
            self.assertEqual(
                snapshot["field_count"],
                len(schema_for_version("contract.v1").semantic_keys),
            )
            self.assertEqual(snapshot["review_status"], "open")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM project_contracts").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stage_form_snapshots").fetchone()[0], 0)

    def test_partial_recognition_materializes_missing_schema_fields_for_manual_review(self):
        job = self.enqueue(idempotency_key="partial-result")

        self.assertTrue(self.worker(_StaticAdapter()).run_once(now=NOW))

        with self.connection_factory() as conn:
            fields = conn.execute(
                """
                SELECT semantic_key, normalized_value_json, source_kind
                FROM extracted_fields
                WHERE recognition_job_id = ?
                ORDER BY semantic_key
                """,
                (job["id"],),
            ).fetchall()

        self.assertEqual(
            {row["semantic_key"] for row in fields},
            set(schema_for_version("contract.v1").semantic_keys),
        )
        missing_owner = next(row for row in fields if row["semantic_key"] == "party.owner")
        self.assertEqual(missing_owner["normalized_value_json"], "null")
        self.assertEqual(missing_owner["source_kind"], "manual")

    def test_duplicate_enqueue_replays_the_same_job(self):
        first = self.enqueue(idempotency_key="same-request")
        second = self.enqueue(idempotency_key="same-request")

        self.assertEqual(first["id"], second["id"])

    def test_expired_running_lease_is_recovered_after_restart(self):
        job = self.enqueue()
        with self.connection_factory() as conn:
            claim_next_recognition_job(
                conn,
                worker_id="dead-worker",
                now="2026-07-13T01:00:00Z",
                lease_seconds=1,
            )

        worker = self.worker(_StaticAdapter(), worker_id="replacement-worker")
        recovered = worker.recover_expired_jobs(now="2026-07-13T01:00:02Z")
        processed = worker.run_once(now="2026-07-13T01:00:03Z")

        self.assertEqual(recovered, 1)
        self.assertTrue(processed)
        with self.connection_factory() as conn:
            self.assertEqual(recognition_job_snapshot(conn, job["id"])["status"], "review_ready")

    def test_result_arriving_after_lease_expiry_is_not_persisted(self):
        job = self.enqueue()
        worker = self.worker(
            _StaticAdapter(),
            lease_seconds=30,
            clock=lambda: "2026-07-13T01:00:31Z",
        )

        with self.assertLogs("server.recognition.worker", level="ERROR"):
            self.assertTrue(worker.run_once(now="2026-07-13T01:00:00Z"))

        with self.connection_factory() as conn:
            snapshot = recognition_job_snapshot(conn, job["id"])
            self.assertEqual(snapshot["status"], "running")
            self.assertEqual(snapshot["field_count"], 0)

    def test_retryable_failure_uses_bounded_backoff_then_manual_required(self):
        job = self.enqueue(max_attempts=2)
        worker = self.worker(_RetryingAdapter())

        self.assertTrue(worker.run_once(now="2026-07-13T01:00:00Z"))
        self.assertFalse(worker.run_once(now="2026-07-13T01:00:01Z"))
        self.assertTrue(worker.run_once(now="2026-07-13T01:00:03Z"))

        with self.connection_factory() as conn:
            snapshot = recognition_job_snapshot(conn, job["id"])
            self.assertEqual(snapshot["status"], "manual_required")
            self.assertEqual(snapshot["attempts"], 2)
            self.assertEqual(snapshot["error_code"], "ocr_provider_timeout")

    def test_malformed_normalized_result_enters_manual_required_without_fields(self):
        job = self.enqueue()

        with self.assertLogs("server.recognition.worker", level="ERROR"):
            self.assertTrue(self.worker(_MalformedAdapter()).run_once(now=NOW))

        with self.connection_factory() as conn:
            snapshot = recognition_job_snapshot(conn, job["id"])
            self.assertEqual(snapshot["status"], "manual_required")
            self.assertEqual(snapshot["error_code"], "ocr_result_invalid")
            self.assertEqual(snapshot["field_count"], 0)

    def test_page_loading_failure_enters_manual_required_without_crashing_worker(self):
        job = self.enqueue()

        def failing_loader(_conn, _job):
            raise ValueError("missing rendered page")

        with self.assertLogs("server.recognition.worker", level="ERROR"):
            processed = self.worker(
                _StaticAdapter(), request_loader=failing_loader
            ).run_once(now=NOW)

        self.assertTrue(processed)
        with self.connection_factory() as conn:
            snapshot = recognition_job_snapshot(conn, job["id"])
            self.assertEqual(snapshot["status"], "manual_required")
            self.assertEqual(snapshot["error_code"], "ocr_page_load_failed")
            self.assertEqual(snapshot["field_count"], 0)

    def test_low_quality_scan_enters_manual_required_before_provider_call(self):
        job = self.enqueue()
        with self.connection_factory() as conn:
            conn.execute(
                "UPDATE document_pages SET quality_score = 0.1 WHERE id = ?",
                (self.page_id,),
            )

        adapter = _StaticAdapter()
        worker = RecognitionWorker(
            connection_factory=self.connection_factory,
            adapter_resolver=lambda _key: adapter,
            storage_root=self.temp.name,
            worker_id="worker-low-quality",
            clock=lambda: NOW,
        )

        with self.assertLogs("server.recognition.worker", level="ERROR"):
            self.assertTrue(worker.run_once(now=NOW))

        with self.connection_factory() as conn:
            snapshot = recognition_job_snapshot(conn, job["id"])
            self.assertEqual(snapshot["status"], "manual_required")
            self.assertEqual(snapshot["error_code"], "ocr_page_quality_low")
            self.assertEqual(snapshot["field_count"], 0)

    def test_stop_waits_for_inflight_job_and_does_not_lose_it(self):
        job = self.enqueue()
        adapter = _BlockingAdapter()
        worker = self.worker(adapter)
        worker.start()
        self.assertTrue(adapter.entered.wait(timeout=2))

        stopped = threading.Event()
        stopper = threading.Thread(target=lambda: (worker.stop(), stopped.set()))
        stopper.start()
        time.sleep(0.05)
        self.assertFalse(stopped.is_set())
        adapter.release.set()
        stopper.join(timeout=3)

        self.assertTrue(stopped.is_set())
        with self.connection_factory() as conn:
            self.assertEqual(recognition_job_snapshot(conn, job["id"])["status"], "review_ready")

    def test_worker_loop_recovers_from_a_transient_internal_exception(self):
        worker = self.worker(_StaticAdapter())
        recovered = threading.Event()
        calls = {"count": 0}

        def flaky_run_once():
            calls["count"] += 1
            if calls["count"] == 1:
                raise sqlite3.OperationalError("temporary database failure")
            recovered.set()
            return False

        worker.run_once = flaky_run_once
        with self.assertLogs("server.recognition.worker", level="ERROR"):
            worker.start()
            self.assertTrue(recovered.wait(timeout=1))
        self.assertTrue(worker.is_alive)
        worker.stop(timeout=1)
        self.assertFalse(worker.is_alive)

    def test_health_payload_reports_configuration_worker_and_queue_counts(self):
        self.enqueue()
        worker = self.worker(_StaticAdapter())
        with self.connection_factory() as conn:
            health = recognition_health_payload(
                conn, recognition_configured=True, worker_alive=worker.is_alive
            )

        self.assertTrue(health["recognitionConfigured"])
        self.assertFalse(health["recognitionWorkerAlive"])
        self.assertEqual(health["recognitionQueue"]["queued"], 1)


if __name__ == "__main__":
    unittest.main()
