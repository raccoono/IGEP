import unittest

from scripts.analyze_b2_retrieval import aggregate_relevance, retrieval_diagnostic, transition_group


class RetrievalDiagnosticTests(unittest.TestCase):
    def test_relevant_at_rank_one(self):
        result = retrieval_diagnostic(["A", "B", "C", "D", "E"], ["A"])
        self.assertEqual(result["issue_relevant_in_top5"], 1)
        self.assertEqual(result["relevant_rank"], 1)

    def test_relevant_at_rank_five(self):
        result = retrieval_diagnostic(["A", "B", "C", "D", "E"], ["E"])
        self.assertEqual(result["issue_relevant_in_top5"], 1)
        self.assertEqual(result["relevant_rank"], 5)

    def test_relevant_absent(self):
        result = retrieval_diagnostic(["A", "B", "C", "D", "E"], ["F"])
        self.assertEqual(result["issue_relevant_in_top5"], 0)
        self.assertEqual(result["number_relevant_in_top5"], 0)
        self.assertIsNone(result["relevant_rank"])

    def test_multiple_relevant_uses_best_rank(self):
        result = retrieval_diagnostic(["A", "B", "C", "D", "E"], ["D", "B"])
        self.assertEqual(result["number_relevant_in_top5"], 2)
        self.assertEqual(result["relevant_rank"], 2)

    def test_unknown_annotation_is_not_a_zero(self):
        result = retrieval_diagnostic(["A", "B", "C", "D", "E"], None)
        self.assertIsNone(result["issue_relevant_in_top5"])
        self.assertIsNone(result["number_relevant_in_top5"])

        aggregate = aggregate_relevance([
            {"issue_relevant_in_top5": 1, "number_relevant_in_top5": 2},
            result,
        ])
        self.assertEqual(aggregate["cases_with_known_issue_annotation"], 1)
        self.assertEqual(aggregate["issue_relevant_in_top5_rate"], 1.0)
        self.assertEqual(aggregate["mean_relevant_statutes_in_top5"], 2.0)

    def test_transition_groups(self):
        self.assertEqual(transition_group(False, True, 0), "A")
        self.assertEqual(transition_group(False, False, 1), "B")
        self.assertEqual(transition_group(False, False, 0), "C")
        self.assertEqual(transition_group(True, False, 1), "D")
        self.assertEqual(transition_group(True, True, 0), "E")
        self.assertEqual(transition_group(False, False, None), "U")


if __name__ == "__main__":
    unittest.main()
