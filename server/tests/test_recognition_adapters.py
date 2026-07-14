import json
import logging
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.recognition.contracts import (
    RecognitionAdapterError,
    RecognitionPage,
    RecognitionRequest,
)
from server.recognition.registry import build_recognition_adapter


class _ProviderState:
    status = 200
    delay_seconds = 0
    response = {}
    request_headers = None
    request_payload = None


class _ProviderHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        _ProviderState.request_headers = dict(self.headers.items())
        _ProviderState.request_payload = json.loads(self.rfile.read(length))
        if _ProviderState.delay_seconds:
            time.sleep(_ProviderState.delay_seconds)
        body = json.dumps(_ProviderState.response).encode("utf-8")
        self.send_response(_ProviderState.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def log_message(self, *_args):
        return


class RecognitionAdapterTests(unittest.TestCase):
    def setUp(self):
        _ProviderState.status = 200
        _ProviderState.delay_seconds = 0
        _ProviderState.response = {}
        _ProviderState.request_headers = None
        _ProviderState.request_payload = None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _ProviderHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/recognize"
        self.request = RecognitionRequest(
            job_id="job-1",
            document_type="construction_contract",
            schema_version="contract.v1",
            pages=(
                RecognitionPage(
                    page_id="page-1",
                    page_number=1,
                    image_bytes=b"scan-bytes",
                    width_px=1000,
                    height_px=2000,
                ),
            ),
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _adapter(self, **overrides):
        settings = {
            "OCR_HTTP_ENDPOINT": self.endpoint,
            "OCR_HTTP_TOKEN": "private-token",
            "OCR_HTTP_TIMEOUT_SECONDS": "1",
            "OCR_ADAPTER_KEY": "approved-http",
        }
        settings.update(overrides)
        return build_recognition_adapter(settings)

    def test_http_adapter_authenticates_and_normalizes_provider_coordinates(self):
        _ProviderState.response = {
            "providerRequestId": "provider-request-1",
            "modelVersion": "layout-model-7",
            "blocks": [
                {
                    "pageId": "page-1",
                    "blockType": "text",
                    "rawText": "建设单位",
                    "confidence": 0.95,
                    "bbox": [100, 200, 400, 100],
                }
            ],
            "fields": [
                {
                    "semanticKey": "party.owner",
                    "rawValue": "江苏某建设单位",
                    "normalizedValue": "江苏某建设单位",
                    "confidence": 0.92,
                    "anchors": [
                        {
                            "pageId": "page-1",
                            "bbox": [100, 200, 400, 100],
                            "sourceText": "江苏某建设单位",
                        }
                    ],
                }
            ],
        }

        result = self._adapter().recognize(self.request)

        self.assertEqual(result.status, "review_ready")
        self.assertEqual(result.provider_request_id, "provider-request-1")
        self.assertEqual(result.adapter_key, "approved-http")
        self.assertEqual(result.blocks[0].bbox, (0.1, 0.1, 0.4, 0.05))
        self.assertEqual(result.fields[0].anchors[0].bbox, (0.1, 0.1, 0.4, 0.05))
        self.assertEqual(
            _ProviderState.request_headers["Authorization"], "Bearer private-token"
        )
        self.assertEqual(_ProviderState.request_payload["jobId"], "job-1")
        self.assertEqual(
            _ProviderState.request_payload["pages"][0]["imageBase64"],
            "c2Nhbi1ieXRlcw==",
        )

    def test_http_statuses_are_mapped_without_leaking_provider_payloads(self):
        cases = (
            (429, "ocr_provider_rate_limited", True),
            (503, "ocr_provider_unavailable", True),
            (422, "ocr_provider_rejected", False),
        )
        for status, code, retryable in cases:
            with self.subTest(status=status):
                _ProviderState.status = status
                _ProviderState.response = {
                    "secretSourceText": "合同中的敏感原文",
                    "token": "provider-secret",
                }
                with self.assertRaises(RecognitionAdapterError) as caught:
                    self._adapter().recognize(self.request)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.retryable, retryable)
                self.assertNotIn("敏感原文", str(caught.exception))
                self.assertNotIn("provider-secret", str(caught.exception))

    def test_timeout_is_retryable(self):
        _ProviderState.delay_seconds = 0.2
        _ProviderState.response = {"providerRequestId": "too-late"}

        with self.assertRaises(RecognitionAdapterError) as caught:
            self._adapter(OCR_HTTP_TIMEOUT_SECONDS="0.05").recognize(self.request)

        self.assertEqual(caught.exception.code, "ocr_provider_timeout")
        self.assertTrue(caught.exception.retryable)

    def test_malformed_response_requires_anchors_and_redacts_logs(self):
        _ProviderState.response = {
            "providerRequestId": "request-with-secret",
            "modelVersion": "model-1",
            "blocks": [],
            "fields": [
                {
                    "semanticKey": "contract.amount",
                    "rawValue": "敏感金额原文",
                    "normalizedValue": "100000",
                    "confidence": 0.9,
                    "anchors": [],
                }
            ],
        }
        with self.assertLogs("server.recognition", level=logging.ERROR) as captured:
            with self.assertRaises(RecognitionAdapterError) as caught:
                self._adapter().recognize(self.request)

        self.assertEqual(caught.exception.code, "ocr_provider_malformed_response")
        logs = "\n".join(captured.output)
        self.assertNotIn("敏感金额原文", logs)
        self.assertNotIn("private-token", logs)
        self.assertNotIn("request-with-secret", logs)

    def test_missing_provider_enters_manual_mode_without_synthesizing_fields(self):
        result = build_recognition_adapter({}).recognize(self.request)

        self.assertEqual(result.status, "manual_required")
        self.assertEqual(result.error_code, "ocr_provider_not_configured")
        self.assertEqual(result.blocks, ())
        self.assertEqual(result.fields, ())

    def test_non_local_provider_requires_https_before_any_document_is_sent(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            build_recognition_adapter(
                {
                    "OCR_HTTP_ENDPOINT": "http://ocr.example.com/recognize",
                    "OCR_HTTP_TOKEN": "private-token",
                }
            )


if __name__ == "__main__":
    unittest.main()
