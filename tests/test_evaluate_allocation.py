import sys
import time
import unittest
import copy
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_gold import validate_instance
from evaluate_allocation import allocation_map, evaluate_records, f1, name
from igep_specs import (
    B2_ALLOCATION_PROMPT_VERSION,
    DIRECT_ALLOCATION_PROMPT_VERSION,
    DIRECT_ALLOCATION_SCHEMA,
    b2_allocation_user_prompt,
    direct_allocation_user_prompt,
)
from run import (
    B2_RETRIEVAL_TOP_K,
    DEFAULT_INPUT,
    DEFAULT_SPLIT_MANIFEST,
    DEFAULT_STATUTE_CORPUS,
    b0_config,
    b0_trace_record,
    b2_config,
    b2_trace_record,
    bm25_retrieve,
    run_allocate,
)


class AllocationEvaluatorTest(unittest.TestCase):
    @staticmethod
    def b0_output(amount=1000):
        return {
            "case_id": "1",
            "cited_articles": ["651"],
            "allocations": [{
                "recipient": "A", "amount": amount, "currency": "VND",
                "share_ratio": None, "basis": "direct allocation",
            }],
            "undistributed_amount": 0,
            "currency": "VND",
            "reason": None,
        }

    def test_name_normalization_removes_honorific(self):
        self.assertEqual(name(" Ông Nguyễn Văn A "), name("Nguyễn Văn A"))

    def test_allocation_map_requires_nonnegative_integer(self):
        with self.assertRaises(ValueError):
            allocation_map([{"recipient":"A","amount":-1}], "allocations")

    def test_duplicate_prediction_recipient_invalidates_only_its_case(self):
        refs = {
            "1": {
                "case_id": "1",
                "reference_articles": ["651"],
                "reference_settlement": [{"recipient": "A", "amount": 1000}],
                "total_reference_amount": 1000,
            },
            "2": {
                "case_id": "2",
                "reference_articles": ["651"],
                "reference_settlement": [{"recipient": "B", "amount": 2000}],
                "total_reference_amount": 2000,
            },
        }
        preds = {
            "1": {
                "case_id": "1",
                "cited_articles": ["651"],
                "allocations": [
                    {"recipient": "Ông A", "amount": 400},
                    {"recipient": "A", "amount": 600},
                ],
            },
            "2": {
                "case_id": "2",
                "cited_articles": ["651"],
                "allocations": [{"recipient": "B", "amount": 2000}],
            },
        }
        raw_prediction = copy.deepcopy(preds)

        report = evaluate_records(refs, preds, "development")

        self.assertEqual(preds, raw_prediction)
        self.assertEqual(report["coverage"]["invalid_cases"], 1)
        self.assertEqual(report["coverage"]["answered_cases"], 2)
        first, second = report["cases"]
        self.assertFalse(first["missing"])
        self.assertTrue(first["invalid"])
        self.assertIn("duplicate normalized recipient", first["validation_errors"][0])
        self.assertEqual(first["heir_f1"], 0.0)
        self.assertFalse(first["allocation_exact"])
        self.assertFalse(first["predicted_total_matches_reference"])
        self.assertFalse(second["invalid"])
        self.assertTrue(second["allocation_exact"])
        # No duplicate merging: only the independently valid case contributes
        # a correct recipient and amount.
        self.assertEqual(report["metrics"]["heir_recall"], 0.5)
        self.assertEqual(report["metrics"]["amount_exact_accuracy"], 0.5)
        self.assertEqual(report["metrics"]["allocation_exact_match"], 0.5)

    def test_f1(self):
        precision, recall, score = f1(1, 2, 2)
        self.assertEqual((precision, recall, score), (0.5, 0.5, 0.5))

    def test_b0_schema_rejects_null_amount(self):
        errors = validate_instance(
            self.b0_output(None), DIRECT_ALLOCATION_SCHEMA,
            DIRECT_ALLOCATION_SCHEMA,
        )
        self.assertTrue(errors)

    def test_b0_schema_rejects_non_integral_amount(self):
        errors = validate_instance(
            self.b0_output(1000.5), DIRECT_ALLOCATION_SCHEMA,
            DIRECT_ALLOCATION_SCHEMA,
        )
        self.assertTrue(errors)

    def test_b0_schema_accepts_nonnegative_integer_amount(self):
        errors = validate_instance(
            self.b0_output(1000), DIRECT_ALLOCATION_SCHEMA,
            DIRECT_ALLOCATION_SCHEMA,
        )
        self.assertEqual(errors, [])

    def test_b0_output_schema_has_no_abstention_status(self):
        self.assertNotIn("status", DIRECT_ALLOCATION_SCHEMA["properties"])
        self.assertNotIn("status", DIRECT_ALLOCATION_SCHEMA["required"])

    def test_b0_trace_contains_frozen_configuration(self):
        config = b0_config()
        trace = b0_trace_record("1", "development", time.perf_counter(), config)
        for field in [
            "method", "model", "reasoning_effort", "max_output_tokens",
            "temperature", "prompt_version", "split", "case_id",
            "timestamp_utc", "timeout_seconds", "attempt_count", "retry_count",
        ]:
            self.assertIn(field, trace)
        self.assertEqual(trace["method"], "b0")
        self.assertEqual(trace["split"], "development")
        self.assertEqual(trace["retry_count"], max(config["attempts"] - 1, 0))

    def test_bm25_retrieval_is_deterministic_and_respects_top_k(self):
        rows = [
            {"id":"VN_A_ART_1","text":"thừa kế theo pháp luật","metadata":{}},
            {"id":"VN_A_ART_2","text":"di chúc hợp pháp","metadata":{}},
            {"id":"VN_A_ART_3","text":"hàng thừa kế thứ nhất","metadata":{}},
        ]
        first = bm25_retrieve(rows, "thừa kế theo pháp luật", top_k=2)
        second = bm25_retrieve(rows, "thừa kế theo pháp luật", top_k=2)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0]["id"], "VN_A_ART_1")

    def test_b2_prompt_contains_case_and_retrieved_statute_context(self):
        hits = [{
            "id":"VN_BLDS_2015_ART_651",
            "text":"Điều 651. Người thừa kế theo pháp luật",
            "metadata": {
                "document_title":"Bộ luật Dân sự 2015",
                "effective_from":"2017-01-01", "effective_to":None,
            },
        }]
        prompt = b2_allocation_user_prompt("1", "Ông A chết.", hits)
        self.assertIn("Ông A chết.", prompt)
        self.assertIn("VN_BLDS_2015_ART_651", prompt)
        self.assertIn("Điều 651", prompt)

    def test_b2_uses_same_allocation_schema_as_b0(self):
        errors = validate_instance(
            self.b0_output(1000), DIRECT_ALLOCATION_SCHEMA,
            DIRECT_ALLOCATION_SCHEMA,
        )
        self.assertEqual(errors, [])

    def test_b0_prompt_and_version_remain_closed_book(self):
        prompt = direct_allocation_user_prompt("1", "Tình huống A")
        self.assertIn("Tình huống A", prompt)
        self.assertNotIn("STATUTE", prompt)
        self.assertEqual(b0_config()["prompt_version"], DIRECT_ALLOCATION_PROMPT_VERSION)

    def test_b2_trace_contains_retrieval_metadata(self):
        config = b2_config()
        trace = b2_trace_record(
            "1", "development", time.perf_counter(), config,
            ["VN_BLDS_2015_ART_651"], DEFAULT_STATUTE_CORPUS, "abc123",
        )
        self.assertEqual(trace["method"], "b2")
        self.assertEqual(trace["prompt_version"], B2_ALLOCATION_PROMPT_VERSION)
        self.assertEqual(trace["retrieval_method"], "bm25")
        self.assertEqual(trace["retrieval_top_k"], B2_RETRIEVAL_TOP_K)
        self.assertEqual(trace["retrieved_statute_ids"], ["VN_BLDS_2015_ART_651"])

    def test_b2_held_out_test_requires_explicit_unlock(self):
        args = SimpleNamespace(
            method="b2", output=None, trace=None, input=DEFAULT_INPUT,
            split="test", allow_held_out_test=False,
            split_manifest=DEFAULT_SPLIT_MANIFEST, case_id=None, limit=1,
            dry_run=True, resume=True, statute_corpus=DEFAULT_STATUTE_CORPUS,
        )
        with self.assertRaises(ValueError):
            run_allocate(args)


if __name__ == "__main__":
    unittest.main()
