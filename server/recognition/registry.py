"""Recognition adapter selection from process configuration."""

from __future__ import annotations

import os

from .http_adapter import HttpRecognitionAdapter
from .manual_adapter import ManualRecognitionAdapter
from .volcengine_adapter import VolcengineOcrAdapter


def recognition_settings_configured(settings=None):
    config = os.environ if settings is None else settings
    provider = str(config.get("OCR_PROVIDER") or "").strip().lower()
    if provider == "volcengine":
        return bool(
            str(config.get("VOLCENGINE_OCR_ACCESS_KEY_ID") or "").strip()
            and str(config.get("VOLCENGINE_OCR_SECRET_ACCESS_KEY") or "").strip()
        )
    return bool(str(config.get("OCR_HTTP_ENDPOINT") or "").strip())


def build_recognition_adapter(settings=None):
    config = os.environ if settings is None else settings
    provider = str(config.get("OCR_PROVIDER") or "").strip().lower()
    volc_access_key = str(
        config.get("VOLCENGINE_OCR_ACCESS_KEY_ID") or ""
    ).strip()
    volc_secret_key = str(
        config.get("VOLCENGINE_OCR_SECRET_ACCESS_KEY") or ""
    ).strip()
    if provider == "volcengine" and volc_access_key and volc_secret_key:
        return VolcengineOcrAdapter(
            access_key_id=volc_access_key,
            secret_access_key=volc_secret_key,
            endpoint=config.get("VOLCENGINE_OCR_ENDPOINT")
            or "https://visual.volcengineapi.com",
            timeout_seconds=config.get("VOLCENGINE_OCR_TIMEOUT_SECONDS") or 30,
        )
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
