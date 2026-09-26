import unittest

from scripts.analyze_b2_retrieval import retrieval_diagnostic
from scripts.analyze_b4_retrieval import (
    case_error_categories,
    end_to_end_transition,
    has_duplicate_recipients,
    retrieval_allocation_group,
    retrieval_transition,
)


class B4RetrievalDiagnosticTest(unittest.TestCase):
    def test_retrieval_relevance_calculation(self):
        result = retrieval_diagnostic(["X", "LAW", "Y"], ["LAW"])
        self.assertEqual(result["issue_relevant_in_top5"], 1)
        self.assertEqual(result["number_relevant_in_top5"], 1)
        self.assertEqual(result["relevant_rank"], 2)

    def test_b2_b4_retrieval_transitions(self):
        self.assertEqual(retrieval_transition(0, 1), "retrieval_improved")
        self.assertEqual(retrieval_transition(1, 0), "retrieval_regressed")
        self.assertEqual(retrieval_transition(1, 1), "retrieval_both_relevant")
        self.assertEqual(retrieval_transition(0, 0), "retrieval_both_missing")

    def test_uncertain_relevance_handling(self):
        self.assertEqual(retrieval_transition(None, 1), "retrieval_uncertain")
        self.assertEqual(retrieval_allocation_group(None, False), "RU_wrong")

    def test_three_way_end_to_end_transition(self):
        self.assertEqual(
            end_to_end_transition(False, False, True),
            "B0_wrong__B2_wrong__B4_correct",
        )

    def test_retrieval_vs_allocation_groups(self):
        self.assertEqual(retrieval_allocation_group(1, True), "R1")
        self.assertEqual(retrieval_allocation_group(1, False), "R2")
        self.assertEqual(retrieval_allocation_group(0, False), "R3")
        self.assertEqual(retrieval_allocation_group(0, True), "R4")

    def test_duplicate_detection_does_not_modify_prediction(self):
        prediction = {"allocations": [
            {"recipient": "Ông A", "amount": 1},
            {"recipient": "A", "amount": 2},
        ]}
        before = repr(prediction)
        self.assertTrue(has_duplicate_recipients(prediction))
        self.assertEqual(repr(prediction), before)

    def test_case_109_classification(self):
        case = {
            "case_id": "109", "b4_allocation_exact": False,
            "b4_heir_f1": 0.0, "b4_amounts_correct": 0,
            "reference_recipients": 2, "retrieval_allocation_group": "R2",
            "b0_allocation_exact": False,
            "b4_predicted_total_matches_reference": False,
            "b4_invalid": True,
        }
        prediction = {"allocations": [
            {"recipient": "T", "amount": 10},
            {"recipient": "T", "amount": 5},
        ]}
        categories = case_error_categories(case, prediction)
        self.assertIn("multi_stage_succession_duplicate_recipient_representation", categories)


if __name__ == "__main__":
    unittest.main()
