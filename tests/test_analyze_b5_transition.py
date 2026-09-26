import unittest

from scripts.analyze_b5_transition import (
    b4_b5_transition,
    case_109_result,
    four_method_pattern,
    retrieval_outcome_group,
    transition_case_ids,
)


class B5TransitionDiagnosticTest(unittest.TestCase):
    def test_b4_b5_transition_classification(self):
        self.assertEqual(b4_b5_transition(True, True), "T1_both_correct")
        self.assertEqual(b4_b5_transition(False, True), "T2_b5_improvement")
        self.assertEqual(b4_b5_transition(True, False), "T3_b5_regression")
        self.assertEqual(b4_b5_transition(False, False), "T4_both_wrong")

    def test_four_method_pattern(self):
        statuses = {"b0": True, "b2": False, "b4": True, "b5": False}
        self.assertEqual(four_method_pattern(statuses), "1010")

    def test_g1_to_g7_grouping(self):
        self.assertEqual(retrieval_outcome_group(1, False, True), "G1_relevant_b4_wrong_b5_correct")
        self.assertEqual(retrieval_outcome_group(1, False, False), "G2_relevant_both_wrong")
        self.assertEqual(retrieval_outcome_group(0, False, True), "G3_missing_b4_wrong_b5_correct")
        self.assertEqual(retrieval_outcome_group(0, False, False), "G4_missing_both_wrong")
        self.assertEqual(retrieval_outcome_group(1, True, False), "G5_relevant_b4_correct_b5_wrong")
        self.assertEqual(retrieval_outcome_group(1, True, True), "G6_relevant_both_correct")
        self.assertEqual(retrieval_outcome_group(None, False, False), "G7_relevance_uncertain")
        self.assertEqual(retrieval_outcome_group(0, True, True), "GX_not_covered_by_defined_G1_G6")

    def test_improvement_and_regression_extraction(self):
        cases = [
            {"case_id": "1", "b4_b5_transition": "T2_b5_improvement"},
            {"case_id": "2", "b4_b5_transition": "T3_b5_regression"},
            {"case_id": "3", "b4_b5_transition": "T4_both_wrong"},
        ]
        self.assertEqual(transition_case_ids(cases, "T2_b5_improvement"), ["1"])
        self.assertEqual(transition_case_ids(cases, "T3_b5_regression"), ["2"])

    def test_case_109_remains_incorrect_after_duplicate_removed(self):
        b4_eval = {"invalid": True, "allocation_exact": False, "heir_f1": 0.0}
        b5_eval = {"invalid": False, "allocation_exact": False, "heir_f1": 0.5}
        b4_prediction = {"allocations": [{"recipient": "T"}, {"recipient": "T"}]}
        b5_prediction = {"allocations": [{"recipient": "T"}, {"recipient": "N"}]}
        b5_trace = {"modules": [
            {"module": "inheritance_issue_analysis", "output": {"multi_stage_issues": ["two stages"]}},
            {"module": "statute_aware_reasoning", "output": {"intermediate_succession_states": [{"opening": 1}, {"opening": 2}]}},
        ]}
        reference = {"reference_settlement": [{"recipient": "T", "amount": 100}]}
        result = case_109_result(b4_eval, b5_eval, b4_prediction, b5_prediction, b5_trace, reference)
        self.assertTrue(result["b4_duplicate_recipients"])
        self.assertFalse(result["b5_duplicate_recipients"])
        self.assertFalse(result["b5_allocation_exact"])
        self.assertEqual(len(result["b5_intermediate_succession_states"]), 2)


if __name__ == "__main__":
    unittest.main()
