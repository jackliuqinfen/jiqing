"""Internal recognition types that are independent from OCR vendors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class RecognitionAdapterError(RuntimeError):
    def __init__(self, code, *, retryable=False, message="识别服务暂时不可用。"):
        super().__init__(message)
        self.code = str(code)
        self.retryable = bool(retryable)


@dataclass(frozen=True)
class RecognitionPage:
    page_id: str
    page_number: int
    image_bytes: bytes
    width_px: int
    height_px: int


@dataclass(frozen=True)
class RecognitionRequest:
    job_id: str
    document_type: str
    schema_version: str
    pages: tuple[RecognitionPage, ...]


@dataclass(frozen=True)
class RecognizedAnchor:
    page_id: str
    bbox: tuple[float, float, float, float]
    source_text: str


@dataclass(frozen=True)
class RecognizedBlock:
    page_id: str
    block_type: str
    raw_text: str
    confidence: float | None
    bbox: tuple[float, float, float, float]
    row_index: int | None = None
    column_index: int | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RecognizedField:
    semantic_key: str
    raw_value: str
    normalized_value: Any
    confidence: float | None
    anchors: tuple[RecognizedAnchor, ...]
    source_kind: str = "ocr"


@dataclass(frozen=True)
class RecognitionResult:
    status: str
    provider_request_id: str
    adapter_key: str
    model_version: str
    blocks: tuple[RecognizedBlock, ...]
    fields: tuple[RecognizedField, ...]
    error_code: str = ""


class RecognitionAdapter(ABC):
    @abstractmethod
    def recognize(self, request: RecognitionRequest) -> RecognitionResult:
        raise NotImplementedError
