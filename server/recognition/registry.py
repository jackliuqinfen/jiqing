"""Recognition adapter selection from process configuration."""

from __future__ import annotations

import os

from .http_adapter import HttpRecognitionAdapter
from .manual_adapter import ManualRecognitionAdapter


def build_recognition_adapter(settings=None):
    config = os.environ if settings is None else settings
    endpoint = str(config.get("OCR_HTTP_ENDPOINT") or "").strip()
    if not endpoint:
        return ManualRecognitionAdapter()
    timeout = float(config.get("OCR_HTTP_TIMEOUT_SECONDS") or 30)
    if timeout <= 0:
        timeout = 30
    return HttpRecognitionAdapter(
        endpoint=endpoint,
        token=config.get("OCR_HTTP_TOKEN") or "",
        timeout_seconds=timeout,
        adapter_key=config.get("OCR_ADAPTER_KEY") or "http",
    )
