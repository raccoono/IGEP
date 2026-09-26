import io
import json
import sys
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_gold import validate_instance
from igep_specs import (
    B5_EXTRACTION_SCHEMA,
    B5_ISSUE_SCHEMA,
    B5_MODULE_ORDER,
    B5_REASONING_SCHEMA,
    DIRECT_ALLOCATION_SCHEMA,
)
from run import (
    B5ModuleError,
    DEFAULT_DENSE_CACHE,
    DEFAULT_INPUT,
    DEFAULT_SPLIT_MANIFEST,
    DEFAULT_STATUTE_CORPUS,
    b5_config,
    b5_trace_record,
    run_allocate,
    run_b5_modules,
)


def extraction(case_id="1"):
    return {
        "case_id": case_id,
        "persons": [{"name": "A", "stated_role": "người chết", "death_date": "2020"}],
        "relationships": [],
        "succession_openings": [{"decedent": "A", "date": "2020", "details": "A chết"}],
        "assets": [{"description": "tiền", "value_vnd": 1000, "stated_ownership": "riêng"}],
        "obligations": [], "wills_gifts_transfers": [], "explicit_uncertainties": [],
    }


def issues(case_id="1"):
    return {
        "case_id": case_id, "succession_modes": ["theo pháp luật"],
        "succession_order": ["mở thừa kế của A"], "will_issues": [],
        "representation_issues": [], "mandatory_share_issues": [],
        "estate_issues": ["xác định 1000 VND"], "obligation_issues": [],
        "multi_stage_issues": [], "other_issues": [],
        "fact_issue_links": [{"fact": "A chết", "issue": "mở thừa kế", "explanation": "Cái chết mở thừa kế"}],
        "unresolved_ambiguities": [],
    }


def reasoning(case_id="1"):
    return {
        "case_id": case_id, "applicable_statutes": ["VN_BLDS_2015_ART_651"],
        "reasoning_steps": [{"step": 1, "facts": ["A chết"], "statutes": ["651"], "conclusion": "chia theo pháp luật"}],
        "intermediate_calculations": [{"description": "di sản", "expression": "1000", "result_vnd": 1000}],
        "intermediate_succession_states": [{"opening": 1, "decedent": "A", "state": "1000 VND chờ chia"}],
        "assumptions": [], "unresolved_ambiguities": [],
    }


def allocation(case_id="1"):
    return {
        "case_id": case_id, "cited_articles": ["651"],
        "allocations": [{"recipient": "B", "amount": 1000, "currency": "VND", "share_ratio": "1", "basis": "thừa kế"}],
        "undistributed_amount": 0, "currency": "VND", "reason": None,
    }


class B5ModularTest(unittest.TestCase):
    def test_structured_extraction_schema(self):
        self.assertEqual(validate_instance(extraction(), B5_EXTRACTION_SCHEMA, B5_EXTRACTION_SCHEMA), [])

    def test_issue_analysis_schema(self):
        self.assertEqual(validate_instance(issues(), B5_ISSUE_SCHEMA, B5_ISSUE_SCHEMA), [])

    def test_statute_reasoning_schema(self):
        self.assertEqual(validate_instance(reasoning(), B5_REASONING_SCHEMA, B5_REASONING_SCHEMA), [])

    def test_final_allocation_schema_is_existing_schema(self):
        self.assertEqual(validate_instance(allocation(), DIRECT_ALLOCATION_SCHEMA, DIRECT_ALLOCATION_SCHEMA), [])

    def test_module_orchestration_has_four_distinct_calls(self):
        outputs = [extraction(), issues(), reasoning(), allocation()]
        calls = []

        def fake_call(system_prompt, user_prompt, **kwargs):
            calls.append((system_prompt, user_prompt, kwargs["schema_name"]))
            index = len(calls) - 1
            return outputs[index], {"id": f"response-{index+1}", "usage": {"input_tokens": 10, "output_tokens": 5}}

        prediction, modules, total = run_b5_modules("1", "A chết.", [], b5_config(), call_fn=fake_call)
        self.assertEqual(prediction, allocation())
        self.assertEqual(len(calls), 4)
        self.assertEqual([module["module"] for module in modules], B5_MODULE_ORDER)
        self.assertEqual(total["input_tokens"], 40)
        self.assertEqual(total["output_tokens"], 20)
        self.assertIn("Dữ kiện có cấu trúc", calls[1][1])
        self.assertIn("Phân tích vấn đề", calls[2][1])
        self.assertIn("Lập luận pháp luật", calls[3][1])

    def test_trace_metadata_and_intermediate_outputs(self):
        config = b5_config()
        modules = [{
            "module": module, "response_id": f"r{i}", "usage": {"total_tokens": 1},
            "output": {"case_id": "1"}, "validation_errors": [],
            "elapsed_seconds": 0.1, "runtime_error": None,
        } for i, module in enumerate(B5_MODULE_ORDER, 1)]
        trace = b5_trace_record(
            "1", "development", time.perf_counter(), config,
            ["S"], ["D"], ["F"], DEFAULT_STATUTE_CORPUS, "hash", modules,
            total_usage={"total_tokens": 4},
        )
        self.assertEqual(trace["method"], "b5")
        self.assertEqual(trace["retrieval_method"], "b4_hybrid")
        self.assertEqual(trace["logical_llm_calls_planned"], 4)
        self.assertEqual(trace["logical_llm_calls_attempted"], 4)
        self.assertEqual(trace["logical_llm_calls_completed"], 4)
        self.assertEqual(trace["retrieved_statute_ids"], ["F"])
        self.assertEqual(trace["modules"][0]["output"], {"case_id": "1"})

    def test_failure_stops_later_modules_and_preserves_trace(self):
        calls = 0

        def failing_call(system_prompt, user_prompt, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return extraction(), {"id": "r1", "usage": {"total_tokens": 3}}
            raise RuntimeError("module failure")

        with self.assertRaises(B5ModuleError) as caught:
            run_b5_modules("1", "A chết.", [], b5_config(), call_fn=failing_call)
        self.assertEqual(calls, 2)
        self.assertEqual(len(caught.exception.modules), 2)
        self.assertEqual(caught.exception.modules[-1]["module"], "inheritance_issue_analysis")
        self.assertEqual(caught.exception.modules[-1]["runtime_error"], "module failure")

    def test_b5_dispatch_and_deterministic_dry_run_without_apis(self):
        args = SimpleNamespace(
            method="b5", output=None, trace=None, input=DEFAULT_INPUT,
            split="development", allow_held_out_test=False,
            split_manifest=DEFAULT_SPLIT_MANIFEST, case_id=["1"], limit=1,
            dry_run=True, resume=True, statute_corpus=DEFAULT_STATUTE_CORPUS,
            dense_cache=DEFAULT_DENSE_CACHE, dense_batch_size=64,
        )
        first = io.StringIO()
        second = io.StringIO()
        with patch("run.voyage_embed", side_effect=AssertionError("Voyage API called")), \
             patch("run.openai_call", side_effect=AssertionError("OpenAI API called")), \
             redirect_stdout(first):
            run_allocate(args)
        with patch("run.voyage_embed", side_effect=AssertionError("Voyage API called")), \
             patch("run.openai_call", side_effect=AssertionError("OpenAI API called")), \
             redirect_stdout(second):
            run_allocate(args)
        self.assertEqual(first.getvalue(), second.getvalue())
        result = json.loads(first.getvalue())
        self.assertEqual(result["method"], "b5")
        self.assertEqual(result["module_execution_order"], B5_MODULE_ORDER)
        self.assertEqual(result["logical_llm_calls"], 4)
        self.assertEqual(len(result["retrieved_statute_ids"]), 5)
        self.assertEqual(len(result["module_requests"]), 4)


if __name__ == "__main__":
    unittest.main()
