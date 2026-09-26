import sys
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from build_gold import validate_instance
from evaluate_allocation import allocation_map, f1, name
from igep_specs import DIRECT_ALLOCATION_SCHEMA
from run import b0_config, b0_trace_record


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


if __name__ == "__main__":
    unittest.main()
