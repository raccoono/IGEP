from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from evaluate import (  # noqa: E402
    DEFAULT_GOLD,
    DEFAULT_SCHEMA,
    counter_metrics,
    evaluate,
    group_records,
    load_records,
    record_fact_counter,
    record_item_counter,
)


class FullSchemaEvaluatorTest(unittest.TestCase):
    def test_asset_identity_does_not_depend_on_free_text_when_value_exists(
        self,
    ) -> None:
        gold = {
            "estates": [
                {
                    "decedent": "A",
                    "assets": [
                        {
                            "asset_id": "A1",
                            "asset_type": "cash",
                            "description": "Bốn tỷ đồng trong tài khoản ngân hàng",
                            "value": 4_000_000_000,
                            "currency": "VND",
                        }
                    ],
                }
            ]
        }
        prediction = {
            "estates": [
                {
                    "decedent": "A",
                    "assets": [
                        {
                            "asset_id": "asset-1",
                            "asset_type": "cash",
                            "description": "Số dư tài khoản",
                            "value": 4_000_000_000,
                            "currency": "VND",
                        }
                    ],
                }
            ]
        }
        gold_records = group_records(gold, "assets")
        prediction_records = group_records(prediction, "assets")
        item = counter_metrics(
            record_item_counter(gold_records),
            record_item_counter(prediction_records),
        )
        content = counter_metrics(
            record_fact_counter(gold_records, content_only=True),
            record_fact_counter(prediction_records, content_only=True),
        )
        self.assertEqual(item["f1"], 1.0)
        self.assertLess(content["f1"], 1.0)

    def test_symmetric_spouse_relation_is_order_invariant(self) -> None:
        left = {
            "relationships": [
                {
                    "subject": "A",
                    "relation": "spouse_of",
                    "object": "B",
                    "qualifiers": ["legal_marriage"],
                    "relationship_status": "active",
                    "start_time": None,
                    "end_time": None,
                    "mutual_care": "not_mentioned",
                }
            ]
        }
        right = {
            "relationships": [
                {
                    "subject": "B",
                    "relation": "spouse_of",
                    "object": "A",
                    "qualifiers": ["legal_marriage"],
                    "relationship_status": "active",
                    "start_time": None,
                    "end_time": None,
                    "mutual_care": "not_mentioned",
                }
            ]
        }
        left_records = group_records(left, "relationships")
        right_records = group_records(right, "relationships")
        self.assertEqual(
            record_item_counter(left_records),
            record_item_counter(right_records),
        )
        self.assertEqual(
            record_fact_counter(left_records, content_only=False),
            record_fact_counter(right_records, content_only=False),
        )

    def test_counter_metrics_penalizes_missing_items(self) -> None:
        result = counter_metrics(
            record_item_counter([("a", {}), ("b", {})]),
            record_item_counter([("a", {})]),
        )
        self.assertEqual(result["true_positive"], 1)
        self.assertEqual(result["false_negative"], 1)
        self.assertAlmostEqual(result["precision"], 1.0)
        self.assertAlmostEqual(result["recall"], 0.5)
        self.assertAlmostEqual(result["f1"], 2 / 3)

    def test_gold_self_evaluation_is_perfect(self) -> None:
        schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8-sig"))
        records = load_records(DEFAULT_GOLD)
        report = evaluate(
            records,
            records,
            schema,
            gold_path=DEFAULT_GOLD,
            prediction_path=DEFAULT_GOLD,
        )
        self.assertEqual(report["coverage"]["evaluated_cases"], 150)
        self.assertEqual(report["validation"]["schema_valid_rate"], 1.0)
        self.assertEqual(report["validation"]["graph_valid_rate"], 1.0)
        self.assertEqual(report["overall"]["content_micro"]["f1"], 1.0)
        self.assertEqual(report["overall"]["case_exact_match_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
