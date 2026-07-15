"""Volcengine OCRNormal adapter with source-preserving page coordinates."""

from __future__ import annotations

import base64
import logging
import socket
from urllib.parse import urlparse

from .contracts import (
    RecognitionAdapter,
    RecognitionAdapterError,
    RecognitionResult,
    RecognizedBlock,
)


LOGGER = logging.getLogger("server.recognition.volcengine_adapter")


class VolcengineOcrAdapter(RecognitionAdapter):
    adapter_key = "volcengine-ocr-normal"
    model_version = "ocr-normal/2020-08-26"

    def __init__(
        self,
        *,
        access_key_id,
        secret_access_key,
        endpoint="https://visual.volcengineapi.com",
        timeout_seconds=30,
        client_factory=None,
    ):
        self.access_key_id = str(access_key_id or "").strip()
        self.secret_access_key = str(secret_access_key or "").strip()
        self.endpoint = str(endpoint or "").strip()
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("VOLCENGINE_OCR_ENDPOINT must use HTTPS")
        self.host = parsed.hostname
        self.timeout_seconds = max(float(timeout_seconds or 30), 1)
        self.client_factory = client_factory or _default_client_factory

    def recognize(self, request):
        client = self.client_factory()
        client.set_ak(self.access_key_id)
        client.set_sk(self.secret_access_key)
        client.set_host(self.host)
        _set_timeout_if_supported(client, self.timeout_seconds)

        request_ids = []
        blocks = []
        for page in request.pages:
            form = {
                "image_base64": base64.b64encode(page.image_bytes).decode("ascii"),
                "mode": "default",
            }
            try:
                response = client.ocr_normal(form)
            except (TimeoutError, socket.timeout):
                raise RecognitionAdapterError(
                    "ocr_provider_timeout",
                    retryable=True,
                    message="识别服务请求超时。",
                ) from None
            except RecognitionAdapterError:
                raise
            except Exception:
                LOGGER.error(
                    "Volcengine OCR request failed: code=ocr_provider_unavailable"
                )
                raise RecognitionAdapterError(
                    "ocr_provider_unavailable",
                    retryable=True,
                    message="识别服务暂时不可用。",
                ) from None

            page_request_id, page_blocks = _normalize_page(response, page)
            request_ids.append(page_request_id)
            blocks.extend(page_blocks)

        return RecognitionResult(
            status="review_ready",
            provider_request_id=",".join(request_ids),
            adapter_key=self.adapter_key,
            model_version=self.model_version,
            blocks=tuple(blocks),
            fields=(),
        )


def _default_client_factory():
    try:
        from volcengine.visual.VisualService import VisualService
    except ImportError:
        raise RecognitionAdapterError(
            "ocr_provider_client_missing",
            retryable=False,
            message="识别服务客户端未安装。",
        ) from None
    return VisualService()


def _set_timeout_if_supported(client, timeout_seconds):
    for method_name in ("set_connection_timeout", "set_socket_timeout"):
        method = getattr(client, method_name, None)
        if callable(method):
            method(timeout_seconds)


def _normalize_page(response, page):
    if not isinstance(response, dict):
        raise _malformed()
    code = int(response.get("code") or 0)
    if code != 10000:
        retryable = code in {429, 63001} or code >= 50000
        raise RecognitionAdapterError(
            "ocr_provider_unavailable" if retryable else "ocr_provider_rejected",
            retryable=retryable,
            message="识别服务暂时不可用。" if retryable else "识别服务拒绝了当前文档。",
        )
    request_id = str(response.get("request_id") or "").strip()
    data = response.get("data")
    if not request_id or not isinstance(data, dict):
        raise _malformed()

    texts = data.get("line_texts")
    rects = data.get("line_rects")
    probabilities = data.get("line_probs") or []
    if not isinstance(texts, list) or not isinstance(rects, list):
        raise _malformed()
    if len(rects) < len(texts):
        raise _malformed()

    blocks = []
    for index, raw_text in enumerate(texts):
        rect = rects[index]
        if not isinstance(rect, dict):
            raise _malformed()
        bbox = _normalized_bbox(rect, page)
        confidence = (
            _normalized_confidence(probabilities[index])
            if index < len(probabilities)
            else None
        )
        blocks.append(
            RecognizedBlock(
                page_id=page.page_id,
                block_type="text",
                raw_text=str(raw_text or ""),
                confidence=confidence,
                bbox=bbox,
                row_index=index,
                metadata={
                    "pageNumber": int(page.page_number),
                    "providerRequestId": request_id,
                },
            )
        )
    return request_id, blocks


def _normalized_bbox(rect, page):
    try:
        page_width = int(page.width_px)
        page_height = int(page.height_px)
        x = float(rect["x"])
        y = float(rect["y"])
        width = float(rect["width"])
        height = float(rect["height"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        raise _malformed() from None
    if page_width <= 0 or page_height <= 0:
        raise _malformed()
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise _malformed()
    if x >= page_width or y >= page_height:
        raise _malformed()

    overflow_x = max(0.0, x + width - page_width)
    overflow_y = max(0.0, y + height - page_height)
    if overflow_x > max(8.0, page_width * 0.005):
        raise _malformed()
    if overflow_y > max(8.0, page_height * 0.005):
        raise _malformed()

    clamped_width = min(x + width, page_width) - x
    clamped_height = min(y + height, page_height) - y
    return tuple(
        round(item, 6)
        for item in (
            x / page_width,
            y / page_height,
            clamped_width / page_width,
            clamped_height / page_height,
        )
    )


def _normalized_confidence(value):
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        raise _malformed() from None
    if 1 < confidence <= 100:
        confidence /= 100
    if confidence < 0 or confidence > 1:
        raise _malformed()
    return round(confidence, 6)


def _malformed():
    return RecognitionAdapterError(
        "ocr_provider_malformed_response",
        retryable=False,
        message="识别服务返回了无法处理的数据。",
    )
