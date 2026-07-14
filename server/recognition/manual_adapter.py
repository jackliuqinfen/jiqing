"""Explicit no-provider adapter that preserves honest manual review."""

from .contracts import RecognitionAdapter, RecognitionResult


class ManualRecognitionAdapter(RecognitionAdapter):
    adapter_key = "manual"

    def recognize(self, request):
        return RecognitionResult(
            status="manual_required",
            provider_request_id="",
            adapter_key=self.adapter_key,
            model_version="",
            blocks=(),
            fields=(),
            error_code="ocr_provider_not_configured",
        )
