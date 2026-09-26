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

from igep_specs import B4_ALLOCATION_PROMPT_VERSION, DIRECT_ALLOCATION_SCHEMA
from run import (
    B4_BM25_CANDIDATE_K,
    B4_DENSE_CANDIDATE_K,
    B4_FINAL_TOP_K,
    B4_RRF_K,
    DEFAULT_INPUT,
    DEFAULT_SPLIT_MANIFEST,
    DEFAULT_STATUTE_CORPUS,
    b4_config,
    b4_trace_record,
    dense_retrieve,
    hybrid_retrieve,
    rrf_fuse,
    run_allocate,
)


def row(identifier, embedding=None):
    return {
        "id": identifier,
        "text": identifier,
        "metadata": {},
        "embedding": embedding,
    }


class B4HybridRetrievalTest(unittest.TestCase):
    def test_rrf_contains_sparse_dense_and_combined_candidates(self):
        sparse = [row("A"), row("B")]
        dense = [row("B"), row("C")]
        result = rrf_fuse(sparse, dense, rrf_k=60, top_k=5)
        by_id = {item["id"]: item for item in result}
        self.assertEqual(set(by_id), {"A", "B", "C"})
        self.assertGreater(by_id["B"]["rrf_score"], by_id["A"]["rrf_score"])
        self.assertIsNone(by_id["A"]["dense_rank"])
        self.assertIsNone(by_id["C"]["bm25_rank"])

    def test_rrf_is_stable_and_ties_break_by_citation_id(self):
        sparse = [row("VN_Z")]
        dense = [row("VN_A")]
        first = rrf_fuse(sparse, dense, rrf_k=60, top_k=5)
        second = rrf_fuse(sparse, dense, rrf_k=60, top_k=5)
        self.assertEqual(first, second)
        self.assertEqual([item["id"] for item in first], ["VN_A", "VN_Z"])

    def test_dense_retrieval_uses_cosine_and_stable_ties(self):
        rows = [row("B", [1.0, 0.0]), row("A", [1.0, 0.0]), row("C", [0.0, 1.0])]
        hits = dense_retrieve(rows, [1.0, 0.0], top_k=2)
        self.assertEqual([item["id"] for item in hits], ["A", "B"])

    def test_fusion_only_uses_configured_candidate_pools_and_top_five(self):
        corpus = [row(f"S{i}", [float(i), 1.0]) for i in range(30)]
        config = b4_config()
        config.update({"bm25_candidate_k": 2, "dense_candidate_k": 3, "final_top_k": 5})
        sparse, dense, fused = hybrid_retrieve(corpus, corpus, "S0", [1.0, 0.0], config)
        candidate_ids = {item["id"] for item in sparse + dense}
        self.assertEqual(len(sparse), 2)
        self.assertEqual(len(dense), 3)
        self.assertLessEqual(len(fused), 5)
        self.assertTrue({item["id"] for item in fused}.issubset(candidate_ids))
        self.assertEqual(fused, hybrid_retrieve(corpus, corpus, "S0", [1.0, 0.0], config)[2])

    def test_b4_frozen_configuration_and_trace(self):
        config = b4_config()
        self.assertEqual(config["prompt_version"], B4_ALLOCATION_PROMPT_VERSION)
        self.assertEqual(config["bm25_candidate_k"], B4_BM25_CANDIDATE_K)
        self.assertEqual(config["dense_candidate_k"], B4_DENSE_CANDIDATE_K)
        self.assertEqual(config["rrf_k"], B4_RRF_K)
        self.assertEqual(config["final_top_k"], B4_FINAL_TOP_K)
        trace = b4_trace_record(
            "1", "development", time.perf_counter(), config,
            ["BM25"], ["DENSE"], ["FUSED"], DEFAULT_STATUTE_CORPUS, "abc",
        )
        self.assertEqual(trace["method"], "b4")
        self.assertEqual(trace["retrieval_method"], "hybrid")
        self.assertEqual(trace["bm25_statute_ids"], ["BM25"])
        self.assertEqual(trace["dense_statute_ids"], ["DENSE"])
        self.assertEqual(trace["retrieved_statute_ids"], ["FUSED"])
        for key in ("dense_model", "dense_metric", "dense_output_dimension", "corpus_sha256"):
            self.assertIn(key, trace)

    def test_b4_dry_run_uses_fake_embeddings_and_no_api(self):
        args = SimpleNamespace(
            method="b4", output=None, trace=None, input=DEFAULT_INPUT,
            split="development", allow_held_out_test=False,
            split_manifest=DEFAULT_SPLIT_MANIFEST, case_id=["1"], limit=1,
            dry_run=True, resume=True, statute_corpus=DEFAULT_STATUTE_CORPUS,
            dense_cache=PROJECT_ROOT / "data/cache/unused-test-cache.jsonl",
            dense_batch_size=64,
        )
        output = io.StringIO()
        with patch("run.voyage_embed", side_effect=AssertionError("Voyage API called")), \
             patch("run.openai_call", side_effect=AssertionError("OpenAI API called")), \
             redirect_stdout(output):
            run_allocate(args)
        result = json.loads(output.getvalue())
        self.assertEqual(result["method"], "b4")
        self.assertEqual(result["dry_run_dense_source"], "deterministic_fake_embeddings")
        self.assertEqual(len(result["bm25_statute_ids"]), 20)
        self.assertEqual(len(result["dense_statute_ids"]), 20)
        self.assertEqual(len(result["retrieved_statute_ids"]), 5)
        self.assertEqual(result["output_schema"], DIRECT_ALLOCATION_SCHEMA)


if __name__ == "__main__":
    unittest.main()
