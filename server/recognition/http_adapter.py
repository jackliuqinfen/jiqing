"""HTTP JSON adapter for approved OCR and layout services."""

from __future__ import annotations

import base64
import json
import logging
import socket
from urllib import error, request as urllib_request
from urllib.parse import urlparse

from .contracts import (
    RecognitionAdapter,
    RecognitionAdapterError,
    RecognitionResult,
    RecognizedAnchor,
    RecognizedBlock,
    RecognizedField,
)


LOGGER = logging.getLogger("server.recognition.http_adapter")


class HttpRecognitionAdapter(RecognitionAdapter):
    def __init__(self, *, endpoint, token, timeout_seconds, adapter_key):
        self.endpoint = str(endpoint).strip()
        parsed_endpoint = urlparse(self.endpoint)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed_endpoint.scheme != "https" and not (
            parsed_endpoint.scheme == "http"
            and parsed_endpoint.hostname in local_hosts
        ):
            raise ValueError(
                "OCR_HTTP_ENDPOINT must use HTTPS unless it targets localhost"
            )
        self.token = str(token or "")
        self.timeout_seconds = float(timeout_seconds)
        self.adapter_key = str(adapter_key or "http").strip() or "http"

    def recognize(self, request):
        page_map = {page.page_id: page for page in request.pages}
        payload = {
            "jobId": request.job_id,
            "documentType": request.document_type,
            "schemaVersion": request.schema_version,
            "pages": [
                {
                    "id": page.page_id,
                    "pageNumber": int(page.page_number),
                    "widthPx": int(page.width_px),
                    "heightPx": int(page.height_px),
                    "imageBase64": base64.b64encode(page.image_bytes).decode("ascii"),
                }
                for page in request.pages
            ],
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        outbound = urllib_request.Request(
            self.endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib_request.urlopen(outbound, timeout=self.timeout_seconds) as response:
                body = response.read()
        except error.HTTPError as exc:
            raise _http_error(exc.code) from None
        except (TimeoutError, socket.timeout):
            raise RecognitionAdapterError(
                "ocr_provider_timeout", retryable=True, message="识别服务请求超时。"
            ) from None
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                code = "ocr_provider_timeout"
                message = "识别服务请求超时。"
            else:
                code = "ocr_provider_unavailable"
                message = "识别服务暂时不可用。"
            raise RecognitionAdapterError(code, retryable=True, message=message) from None

        try:
            provider = json.loads(body.decode("utf-8"))
            return _normalize_result(provider, page_map, self.adapter_key)
        except RecognitionAdapterError:
            LOGGER.error(
                "OCR provider response rejected: code=ocr_provider_malformed_response adapter=%s",
                self.adapter_key,
            )
            raise
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.error(
                "OCR provider response rejected: code=ocr_provider_malformed_response adapter=%s",
                self.adapter_key,
            )
            raise RecognitionAdapterError(
                "ocr_provider_malformed_response",
                retryable=False,
                message="识别服务返回了无法处理的数据。",
            ) from None


def _http_error(status):
    if int(status) == 429:
        return RecognitionAdapterError(
            "ocr_provider_rate_limited",
            retryable=True,
            message="识别服务当前请求过多，请稍后重试。",
        )
    if int(status) >= 500:
        return RecognitionAdapterError(
            "ocr_provider_unavailable",
            retryable=True,
            message="识别服务暂时不可用。",
        )
    return RecognitionAdapterError(
        "ocr_provider_rejected",
        retryable=False,
        message="识别服务拒绝了当前文档。",
    )


def _normalize_result(provider, page_map, adapter_key):
    provider_request_id = _required_text(provider, "providerRequestId")
    model_version = _required_text(provider, "modelVersion")
    blocks = tuple(
        _normalize_block(block, page_map) for block in _required_list(provider, "blocks")
    )
    fields = tuple(
        _normalize_field(field, page_map) for field in _required_list(provider, "fields")
    )
    return RecognitionResult(
        status="review_ready",
        provider_request_id=provider_request_id,
        adapter_key=adapter_key,
        model_version=model_version,
        blocks=blocks,
        fields=fields,
    )


def _normalize_block(value, page_map):
    page_id = _known_page(value, page_map)
    return RecognizedBlock(
        page_id=page_id,
        block_type=_required_text(value, "blockType"),
        raw_text=str(value.get("rawText") or ""),
        confidence=_confidence(value.get("confidence")),
        bbox=_normalize_bbox(value.get("bbox"), page_map[page_id]),
        row_index=_optional_int(value.get("rowIndex")),
        column_index=_optional_int(value.get("columnIndex")),
        metadata=dict(value.get("metadata") or {}),
    )


def _normalize_field(value, page_map):
    anchors_value = _required_list(value, "anchors")
    if not anchors_value:
        raise _malformed()
    anchors = tuple(_normalize_anchor(anchor, page_map) for anchor in anchors_value)
    return RecognizedField(
        semantic_key=_required_text(value, "semanticKey"),
        raw_value=str(value.get("rawValue") or ""),
        normalized_value=value.get("normalizedValue"),
        confidence=_confidence(value.get("confidence")),
        anchors=anchors,
        source_kind="ocr",
    )


def _normalize_anchor(value, page_map):
    page_id = _known_page(value, page_map)
    return RecognizedAnchor(
        page_id=page_id,
        bbox=_normalize_bbox(value.get("bbox"), page_map[page_id]),
        source_text=str(value.get("sourceText") or ""),
    )


def _normalize_bbox(value, page):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise _malformed()
    coords = tuple(float(item) for item in value)
    if any(item > 1 for item in coords):
        x, y, width, height = coords
        coords = (
            x / int(page.width_px),
            y / int(page.height_px),
            width / int(page.width_px),
            height / int(page.height_px),
        )
    x, y, width, height = coords
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > 1.000001
        or y + height > 1.000001
    ):
        raise _malformed()
    return tuple(round(item, 6) for item in coords)


def _known_page(value, page_map):
    page_id = _required_text(value, "pageId")
    if page_id not in page_map:
        raise _malformed()
    return page_id


def _required_text(value, key):
    text = str(value.get(key) or "").strip()
    if not text:
        raise _malformed()
    return text


def _required_list(value, key):
    result = value.get(key)
    if not isinstance(result, list):
        raise _malformed()
    return result


def _confidence(value):
    if value in (None, ""):
        return None
    parsed = float(value)
    if parsed < 0 or parsed > 1:
        raise _malformed()
    return parsed


def _optional_int(value):
    return None if value in (None, "") else int(value)


def _malformed():
    return RecognitionAdapterError(
        "ocr_provider_malformed_response",
        retryable=False,
        message="识别服务返回了无法处理的数据。",
    )
