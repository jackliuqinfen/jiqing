"""Provider-neutral recognition contracts and adapters."""

from .contracts import (
    RecognitionAdapter,
    RecognitionAdapterError,
    RecognitionPage,
    RecognitionRequest,
    RecognitionResult,
    RecognizedAnchor,
    RecognizedBlock,
    RecognizedField,
)

__all__ = [
    "RecognitionAdapter",
    "RecognitionAdapterError",
    "RecognitionPage",
    "RecognitionRequest",
    "RecognitionResult",
    "RecognizedAnchor",
    "RecognizedBlock",
    "RecognizedField",
]
