import unittest
from decimal import Decimal

from server.lifecycle import (
    STAGE_ORDER,
    audit_start_failures,
    contract_gate_failures,
    next_stage,
    stage_label,
    validate_adjacent_transition,
)


class LifecyclePolicyTests(unittest.TestCase):
    def test_adjacent_transition_is_accepted(self):
        self.assertEqual(
            validate_adjacent_transition("awarded", "contract_signed"),
            [],
        )

    def test_stage_helpers_return_the_next_stage_and_label(self):
        self.assertEqual(next_stage("awarded"), "contract_signed")
        self.assertEqual(
            {stage: stage_label(stage) for stage in (
                "awarded",
                "contract_signed",
                "under_construction",
                "completed_acceptance",
                "pending_submission",
                "first_audit",
                "second_audit",
                "conclusion",
                "archived",
            )},
            {
                "awarded": "已中标",
                "contract_signed": "已签订合同",
                "under_construction": "已进场施工中",
                "completed_acceptance": "已竣工验收",
                "pending_submission": "待报审",
                "first_audit": "一审中",
                "second_audit": "二审中",
                "conclusion": "已定案结论",
                "archived": "已归档",
            },
        )

    def test_every_adjacent_transition_is_accepted(self):
        for current, target in zip(STAGE_ORDER, STAGE_ORDER[1:]):
            with self.subTest(current=current, target=target):
                self.assertEqual(
                    validate_adjacent_transition(current, target),
                    [],
                )

    def test_jump_transition_is_rejected(self):
        failures = validate_adjacent_transition("awarded", "under_construction")

        self.assertEqual(failures[0]["code"], "non_adjacent_transition")
        self.assertEqual(failures[0]["field"], "toStage")

    def test_terminal_stage_transition_is_rejected(self):
        failures = validate_adjacent_transition("archived", "archived")

        self.assertEqual(failures[0]["code"], "terminal_stage")
        self.assertEqual(failures[0]["field"], "toStage")

    def test_archived_has_no_next_stage(self):
        self.assertIsNone(next_stage("archived"))

    def test_unknown_stages_are_rejected(self):
        self.assertIsNone(next_stage("unknown"))

        current_failures = validate_adjacent_transition("unknown", "awarded")
        self.assertEqual(current_failures[0]["code"], "invalid_current_stage")
        self.assertEqual(current_failures[0]["field"], "currentStage")

        target_failures = validate_adjacent_transition("awarded", "unknown")
        self.assertEqual(target_failures[0]["code"], "invalid_target_stage")
        self.assertEqual(target_failures[0]["field"], "toStage")

    def test_contract_gate_reports_every_missing_requirement(self):
        failures = contract_gate_failures({}, has_contract_file=False)

        self.assertEqual(
            [(failure["code"], failure["field"]) for failure in failures],
            [
                ("contract_date_required", "contractDate"),
                ("contract_amount_required", "contractAmount"),
                ("owner_unit_required", "ownerUnit"),
                ("construction_unit_required", "constructionUnit"),
                ("contract_file_required", "contractFile"),
            ],
        )

    def test_contract_gate_accepts_complete_contract_facts(self):
        project = {
            "contract_date": "2026-07-11",
            "contract_amount": 1,
            "owner_unit": "建设单位",
            "construction_unit": "施工单位",
        }

        self.assertEqual(contract_gate_failures(project, has_contract_file=True), [])

    def test_contract_gate_accepts_camel_case_contract_subjects(self):
        project = {
            "contractDate": "2026-07-11",
            "contractAmount": 1,
            "ownerUnit": "建设单位",
            "constructionUnit": "施工单位",
        }

        self.assertEqual(contract_gate_failures(project, has_contract_file=True), [])

    def test_contractor_name_does_not_satisfy_contract_subject_requirements(self):
        failures = contract_gate_failures(
            {
                "contract_date": "2026-07-11",
                "contract_amount": 1,
                "contractor_name": "施工单位",
            },
            has_contract_file=True,
        )

        self.assertEqual(
            [(failure["code"], failure["field"]) for failure in failures],
            [
                ("owner_unit_required", "ownerUnit"),
                ("construction_unit_required", "constructionUnit"),
            ],
        )

    def test_contract_gate_rejects_non_finite_amounts(self):
        for amount in (
            "NaN",
            "Infinity",
            "-Infinity",
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(amount=amount):
                failures = contract_gate_failures(
                    {
                        "contract_date": "2026-07-11",
                        "contract_amount": amount,
                        "owner_unit": "建设单位",
                        "construction_unit": "施工单位",
                    },
                    has_contract_file=True,
                )

                self.assertEqual(failures[0]["code"], "contract_amount_required")
                self.assertEqual(failures[0]["field"], "contractAmount")

    def test_audit_start_is_rejected_before_pending_submission(self):
        failures = audit_start_failures(
            {"project_status": "completed_acceptance", "submitted_amount": 100},
        )

        self.assertEqual(failures[0]["code"], "audit_stage_not_reached")
        self.assertEqual(failures[0]["field"], "projectStatus")

    def test_audit_start_requires_a_positive_submitted_amount(self):
        failures = audit_start_failures(
            {"project_status": "pending_submission", "submitted_amount": 0},
        )

        self.assertEqual(failures[0]["code"], "submitted_amount_required")
        self.assertEqual(failures[0]["field"], "submittedAmount")

    def test_audit_start_accepts_only_the_three_audit_stages(self):
        for stage in ("pending_submission", "first_audit", "second_audit"):
            with self.subTest(stage=stage):
                self.assertEqual(
                    audit_start_failures(
                        {"project_status": stage, "submitted_amount": 100},
                    ),
                    [],
                )

    def test_audit_start_rejects_conclusion_and_archived(self):
        for stage in ("conclusion", "archived"):
            with self.subTest(stage=stage):
                failures = audit_start_failures(
                    {"project_status": stage, "submitted_amount": 100},
                )

                self.assertEqual(failures[0]["code"], "audit_stage_not_reached")
                self.assertEqual(failures[0]["field"], "projectStatus")

    def test_audit_start_rejects_unknown_stage(self):
        failures = audit_start_failures(
            {"project_status": "unknown", "submitted_amount": 100},
        )

        self.assertEqual(failures[0]["code"], "audit_stage_not_reached")
        self.assertEqual(failures[0]["field"], "projectStatus")

    def test_audit_start_rejects_non_finite_submitted_amounts(self):
        for amount in (
            "NaN",
            "Infinity",
            "-Infinity",
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(amount=amount):
                failures = audit_start_failures(
                    {
                        "project_status": "pending_submission",
                        "submitted_amount": amount,
                    },
                )

                self.assertEqual(failures[0]["code"], "submitted_amount_required")
                self.assertEqual(failures[0]["field"], "submittedAmount")


if __name__ == "__main__":
    unittest.main()
