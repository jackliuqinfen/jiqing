import unittest

from server.document_requirements import applicable_required_categories


class DocumentRequirementPolicyTests(unittest.TestCase):
    def setUp(self):
        self.categories = [
            {
                "category_key": "contract",
                "required": 1,
                "enabled": 1,
                "required_from_stage": "contract_signed",
            },
            {
                "category_key": "drawing",
                "required": 1,
                "enabled": 1,
                "required_from_stage": "under_construction",
            },
            {
                "category_key": "settlement_book",
                "required": 1,
                "enabled": 1,
                "required_from_stage": "pending_submission",
            },
            {
                "category_key": "first_audit",
                "required": 1,
                "enabled": 1,
                "required_from_stage": "first_audit",
            },
            {
                "category_key": "second_audit",
                "required": 1,
                "enabled": 1,
                "required_from_stage": "second_audit",
            },
            {
                "category_key": "payment",
                "required": 0,
                "enabled": 1,
                "required_from_stage": "conclusion",
            },
        ]

    def test_contract_stage_does_not_require_future_documents(self):
        required = applicable_required_categories(
            self.categories,
            "contract_signed",
        )

        self.assertEqual(
            [category["category_key"] for category in required],
            ["contract"],
        )

    def test_each_document_becomes_required_only_after_its_start_stage(self):
        required = applicable_required_categories(
            self.categories,
            "first_audit",
        )

        self.assertEqual(
            [category["category_key"] for category in required],
            ["contract", "drawing", "settlement_book", "first_audit"],
        )

    def test_unknown_project_stage_does_not_create_false_missing_documents(self):
        self.assertEqual(
            applicable_required_categories(self.categories, "unknown"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
