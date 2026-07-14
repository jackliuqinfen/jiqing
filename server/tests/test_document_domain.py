import unittest

from server.document_domain import (
    DocumentStatus,
    DocumentType,
    RecognitionStatus,
    ReviewDecisionType,
    ReviewStatus,
    allowed_document_types,
    critical_fields_for,
    validate_status_transition,
)


class DocumentDomainTests(unittest.TestCase):
    def test_phase_one_document_types_are_explicit(self):
        self.assertEqual(
            {item.value for item in DocumentType},
            {
                "construction_contract",
                "completion_acceptance_certificate",
                "final_audit_determination",
            },
        )

    def test_document_recognition_and_review_statuses_are_separate(self):
        self.assertIn("recognition_queued", {item.value for item in DocumentStatus})
        self.assertIn("review_ready", {item.value for item in DocumentStatus})
        self.assertEqual(RecognitionStatus.MANUAL_REQUIRED.value, "manual_required")
        self.assertEqual(ReviewStatus.CONFIRMED.value, "confirmed")
        self.assertEqual(ReviewDecisionType.UNRECOGNIZED.value, "unrecognized")

    def test_contract_is_available_only_at_contract_handoff(self):
        self.assertEqual(
            allowed_document_types("contract_handoff"),
            (DocumentType.CONSTRUCTION_CONTRACT.value,),
        )
        self.assertNotIn(
            DocumentType.CONSTRUCTION_CONTRACT.value,
            allowed_document_types("under_construction"),
        )

    def test_acceptance_is_not_available_before_acceptance_stage(self):
        self.assertNotIn(
            DocumentType.COMPLETION_ACCEPTANCE_CERTIFICATE.value,
            allowed_document_types("under_construction"),
        )
        self.assertIn(
            DocumentType.COMPLETION_ACCEPTANCE_CERTIFICATE.value,
            allowed_document_types("completed_acceptance"),
        )

    def test_final_determination_is_not_available_before_audit_stage(self):
        self.assertNotIn(
            DocumentType.FINAL_AUDIT_DETERMINATION.value,
            allowed_document_types("pending_submission"),
        )
        self.assertNotIn(
            DocumentType.FINAL_AUDIT_DETERMINATION.value,
            allowed_document_types("second_audit"),
        )
        self.assertIn(
            DocumentType.FINAL_AUDIT_DETERMINATION.value,
            allowed_document_types("conclusion"),
        )

    def test_contract_critical_fields_require_individual_review(self):
        fields = critical_fields_for(DocumentType.CONSTRUCTION_CONTRACT.value)
        self.assertIn("party.owner", fields)
        self.assertIn("party.contractor", fields)
        self.assertIn("contract.amount", fields)
        self.assertIn("contract.payment_terms", fields)

    def test_unknown_document_type_has_no_critical_fields(self):
        self.assertEqual(critical_fields_for("unknown"), frozenset())

    def test_valid_document_status_transition_has_no_blocker(self):
        self.assertEqual(validate_status_transition("uploaded", "rendering"), [])
        self.assertEqual(
            validate_status_transition("recognizing", "review_ready"),
            [],
        )

    def test_invalid_document_status_transition_is_structured(self):
        blockers = validate_status_transition("uploaded", "confirmed")
        self.assertEqual(len(blockers), 1)
        self.assertEqual(blockers[0]["code"], "invalid_document_status_transition")
        self.assertEqual(blockers[0]["field"], "status")
        self.assertEqual(blockers[0]["currentStatus"], "uploaded")
        self.assertEqual(blockers[0]["targetStatus"], "confirmed")

    def test_unknown_status_transition_is_rejected(self):
        blockers = validate_status_transition("missing", "rendering")
        self.assertEqual(blockers[0]["code"], "unknown_document_status")


if __name__ == "__main__":
    unittest.main()
