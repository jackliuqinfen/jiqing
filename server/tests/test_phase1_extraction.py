import unittest

from server.recognition.normalizers import normalize_extracted_fields
from server.recognition.schemas import schema_for_version
from server.recognition.validators import (
    build_review_blockers,
    validate_extracted_fields,
)


def _field(key, raw_value, *, anchors=True):
    return {
        "semantic_key": key,
        "raw_value": raw_value,
        "confidence": 0.9,
        "anchors": ([{"id": f"anchor-{key}"}] if anchors else []),
    }


def _values(fields):
    return {item["semantic_key"]: item["normalized_value"] for item in fields}


class PhaseOneExtractionTests(unittest.TestCase):
    def test_phase_one_schemas_expose_only_the_confirmed_semantic_keys(self):
        contract = schema_for_version("contract.v1")
        acceptance = schema_for_version("acceptance.v1")
        determination = schema_for_version("final_determination.v1")

        self.assertEqual(contract.document_type, "construction_contract")
        self.assertIn("contract.payment_terms", contract.semantic_keys)
        self.assertIn("acceptance.signatures", acceptance.semantic_keys)
        self.assertIn("audit.final_settlement_amount", determination.semantic_keys)
        self.assertNotIn("audit.final_settlement_amount", contract.semantic_keys)

    def test_money_dates_and_multiline_clauses_are_typed_without_wan_rounding(self):
        normalized = normalize_extracted_fields(
            [
                _field("contract.amount", "人民币壹佰贰拾叁万肆仟伍佰陆拾柒元捌角玖分"),
                _field("contract.signed_date", "2026 年 7 / 10 日"),
                _field("contract.payment_terms", "竣工验收后支付60%\n\n审计完成后支付至97%"),
            ],
            "contract.v1",
        )
        values = _values(normalized)

        self.assertEqual(values["contract.amount"], 123456789)
        self.assertEqual(values["contract.signed_date"], "2026-07-10")
        self.assertEqual(
            values["contract.payment_terms"],
            ["竣工验收后支付60%", "审计完成后支付至97%"],
        )

    def test_arabic_wan_amount_is_converted_to_integer_fen(self):
        normalized = normalize_extracted_fields(
            [_field("audit.final_settlement_amount", "261.638174 万元")],
            "final_determination.v1",
        )

        self.assertEqual(
            normalized[0]["normalized_value"],
            261638174,
        )

    def test_uppercase_amount_mismatch_blocks_final_determination(self):
        fields = normalize_extracted_fields(
            [
                _field("audit.final_settlement_amount", "1000000.00 元"),
                _field("audit.uppercase_amount", "人民币玖拾万元整"),
            ],
            "final_determination.v1",
        )

        issues = validate_extracted_fields("final_audit_determination", fields)

        self.assertIn("uppercase_amount_mismatch", {item["code"] for item in issues})

    def test_acceptance_before_completion_and_not_passed_are_blockers(self):
        fields = normalize_extracted_fields(
            [
                _field("project.completion_date", "2026-07-12"),
                _field("acceptance.date", "2026-07-10"),
                _field("acceptance.conclusion", "验收未通过，整改后复验"),
            ],
            "acceptance.v1",
        )

        issues = validate_extracted_fields(
            "completion_acceptance_certificate", fields
        )
        codes = {item["code"] for item in issues}

        self.assertIn("acceptance_before_completion", codes)
        self.assertIn("acceptance_not_passed", codes)

    def test_final_amount_equations_and_percentage_decimal_errors_block(self):
        fields = normalize_extracted_fields(
            [
                _field("audit.submitted_amount", "1000000 元"),
                _field("audit.engineering_determined_amount", "950000 元"),
                _field("audit.review_fee_deduction", "10000 元"),
                _field("audit.final_settlement_amount", "930000 元"),
                _field("audit.reduction_amount", "50000 元"),
                _field("audit.reduction_rate", "0.05%"),
            ],
            "final_determination.v1",
        )

        issues = validate_extracted_fields("final_audit_determination", fields)
        codes = {item["code"] for item in issues}

        self.assertIn("final_settlement_equation_conflict", codes)
        self.assertIn("suspected_percentage_decimal_error", codes)
        self.assertNotIn("reduction_amount_equation_conflict", codes)

    def test_critical_fields_require_anchor_and_individual_review(self):
        fields = normalize_extracted_fields(
            [
                _field("project.name", "某工程"),
                _field("party.owner", "某建设单位", anchors=False),
                _field("party.contractor", "某施工单位"),
                _field("contract.amount", "100万元"),
                _field("contract.signed_date", "2026-07-10"),
                _field("contract.payment_terms", "验收后支付60%"),
            ],
            "contract.v1",
        )

        blockers = build_review_blockers(
            "construction_contract",
            fields,
            reviewer_decisions={"project.name": {"decision": "accepted"}},
        )
        codes_by_field = {(item["code"], item["field"]) for item in blockers}

        self.assertIn(("evidence_anchor_missing", "party.owner"), codes_by_field)
        self.assertIn(("critical_field_unresolved", "contract.amount"), codes_by_field)
        self.assertNotIn(("critical_field_unresolved", "project.name"), codes_by_field)

    def test_manually_completed_missing_field_does_not_require_a_fake_ocr_anchor(self):
        fields = normalize_extracted_fields(
            [
                _field("project.name", "某工程"),
                _field("party.owner", "", anchors=False),
            ],
            "contract.v1",
        )
        decisions = {
            "project.name": {"decision": "accepted"},
            "party.owner": {"decision": "modified"},
        }
        effective = [
            fields[0],
            {
                **fields[1],
                "normalized_value": "人工补录建设单位",
                "validation_status": "valid",
            },
        ]

        blockers = build_review_blockers(
            "construction_contract",
            effective,
            reviewer_decisions=decisions,
        )

        self.assertNotIn(
            ("evidence_anchor_missing", "party.owner"),
            {(item["code"], item["field"]) for item in blockers},
        )

    def test_confirmed_manual_source_does_not_require_a_fake_ocr_anchor(self):
        fields = normalize_extracted_fields(
            [{**_field("project.name", "人工录入工程", anchors=False), "source_kind": "manual"}],
            "contract.v1",
        )

        blockers = build_review_blockers(
            "construction_contract",
            fields,
            reviewer_decisions={"project.name": {"decision": "accepted"}},
        )

        self.assertNotIn(
            ("evidence_anchor_missing", "project.name"),
            {(item["code"], item["field"]) for item in blockers},
        )


if __name__ == "__main__":
    unittest.main()
