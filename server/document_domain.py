"""Domain policy for scanned lifecycle evidence and human review."""

from __future__ import annotations

from enum import Enum


class DocumentType(str, Enum):
    CONSTRUCTION_CONTRACT = "construction_contract"
    COMPLETION_ACCEPTANCE_CERTIFICATE = "completion_acceptance_certificate"
    FINAL_AUDIT_DETERMINATION = "final_audit_determination"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    RENDERING = "rendering"
    RECOGNITION_QUEUED = "recognition_queued"
    RECOGNIZING = "recognizing"
    REVIEW_READY = "review_ready"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    CORRECTION_REQUIRED = "correction_required"
    MANUAL_REQUIRED = "manual_required"
    QUARANTINED = "quarantined"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class RecognitionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    REVIEW_READY = "review_ready"
    MANUAL_REQUIRED = "manual_required"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


class ReviewDecisionType(str, Enum):
    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"
    UNRECOGNIZED = "unrecognized"


DOCUMENT_TRANSITIONS = {
    "uploaded": frozenset({"rendering", "quarantined"}),
    "rendering": frozenset({"recognition_queued", "manual_required", "failed"}),
    "recognition_queued": frozenset({"recognizing", "manual_required", "failed"}),
    "recognizing": frozenset({"review_ready", "manual_required", "failed"}),
    "review_ready": frozenset({"in_review", "superseded"}),
    "in_review": frozenset({"confirmed", "review_ready", "superseded"}),
    "confirmed": frozenset({"correction_required", "superseded"}),
    "correction_required": frozenset({"in_review", "superseded"}),
    "manual_required": frozenset({"review_ready", "failed", "superseded"}),
    "quarantined": frozenset({"uploaded", "superseded"}),
    "failed": frozenset({"recognition_queued", "manual_required", "superseded"}),
    "superseded": frozenset(),
}


_DOCUMENT_TYPES_BY_STAGE = {
    "contract_handoff": (DocumentType.CONSTRUCTION_CONTRACT.value,),
    "completed_acceptance": (
        DocumentType.COMPLETION_ACCEPTANCE_CERTIFICATE.value,
    ),
    "conclusion": (DocumentType.FINAL_AUDIT_DETERMINATION.value,),
}


CRITICAL_FIELDS = {
    DocumentType.CONSTRUCTION_CONTRACT.value: frozenset(
        {
            "project.name",
            "party.owner",
            "party.contractor",
            "contract.amount",
            "contract.signed_date",
            "contract.payment_terms",
        }
    ),
    DocumentType.COMPLETION_ACCEPTANCE_CERTIFICATE.value: frozenset(
        {
            "project.name",
            "party.contractor",
            "acceptance.date",
            "acceptance.conclusion",
        }
    ),
    DocumentType.FINAL_AUDIT_DETERMINATION.value: frozenset(
        {
            "project.name",
            "party.owner",
            "party.contractor",
            "audit.engineering_determined_amount",
            "audit.final_settlement_amount",
            "audit.determination_date",
        }
    ),
}


def allowed_document_types(stage):
    """Return Phase 1 document types that can form a fact at *stage*."""
    return _DOCUMENT_TYPES_BY_STAGE.get(str(stage or "").strip(), ())


def critical_fields_for(document_type):
    """Return protected semantic fields requiring individual human review."""
    return CRITICAL_FIELDS.get(str(document_type or "").strip(), frozenset())


def validate_status_transition(current, target):
    """Return a structured blocker list for a document status transition."""
    current_value = str(current or "").strip()
    target_value = str(target or "").strip()
    if current_value not in DOCUMENT_TRANSITIONS or target_value not in DOCUMENT_TRANSITIONS:
        return [
            {
                "code": "unknown_document_status",
                "field": "status",
                "message": "文档处理状态无效。",
                "currentStatus": current_value,
                "targetStatus": target_value,
            }
        ]
    if target_value not in DOCUMENT_TRANSITIONS[current_value]:
        return [
            {
                "code": "invalid_document_status_transition",
                "field": "status",
                "message": "当前文档状态不允许执行该操作。",
                "currentStatus": current_value,
                "targetStatus": target_value,
            }
        ]
    return []
