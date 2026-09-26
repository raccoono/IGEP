#!/usr/bin/env python3
"""Offline B4 retrieval and B0/B2/B4 transition diagnostic."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:  # Direct CLI execution.
    from analyze_b2_retrieval import CASE_ISSUES, DIAGNOSTIC_VERSION as B2_ANNOTATION_VERSION
    from analyze_b2_retrieval import index_unique, load_jsonl, retrieval_diagnostic
    from evaluate_allocation import name
except ModuleNotFoundError:  # Imported as ``scripts.analyze_b4_retrieval`` in tests.
    from scripts.analyze_b2_retrieval import CASE_ISSUES, DIAGNOSTIC_VERSION as B2_ANNOTATION_VERSION
    from scripts.analyze_b2_retrieval import index_unique, load_jsonl, retrieval_diagnostic
    from scripts.evaluate_allocation import name


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_VERSION = "b4-retrieval-transition-diagnostic-v1"


def retrieval_transition(b2_relevant: int | None, b4_relevant: int | None) -> str:
    if b2_relevant is None or b4_relevant is None:
        return "retrieval_uncertain"
    if not b2_relevant and b4_relevant:
        return "retrieval_improved"
    if b2_relevant and not b4_relevant:
        return "retrieval_regressed"
    if b2_relevant and b4_relevant:
        return "retrieval_both_relevant"
    return "retrieval_both_missing"


def end_to_end_transition(b0_exact: bool, b2_exact: bool, b4_exact: bool) -> str:
    state = lambda exact: "correct" if exact else "wrong"
    return f"B0_{state(b0_exact)}__B2_{state(b2_exact)}__B4_{state(b4_exact)}"


def retrieval_allocation_group(relevant: int | None, allocation_exact: bool) -> str:
    if relevant is None:
        return "RU_correct" if allocation_exact else "RU_wrong"
    if relevant and allocation_exact:
        return "R1"
    if relevant and not allocation_exact:
        return "R2"
    if not relevant and not allocation_exact:
        return "R3"
    return "R4"


def has_duplicate_recipients(prediction: dict[str, Any]) -> bool:
    normalized = [name(str(row.get("recipient", ""))) for row in prediction.get("allocations", [])]
    return len(normalized) != len(set(normalized))


def case_error_categories(case: dict[str, Any], prediction: dict[str, Any]) -> list[str]:
    if case["b4_allocation_exact"]:
        return []
    categories: list[str] = []
    if case["b4_heir_f1"] < 1.0:
        categories.append("wrong_heir_identification")
    if case.get("b4_amounts_correct", 0) < case.get("reference_recipients", 0):
        categories.append("wrong_monetary_allocation")
    if case["retrieval_allocation_group"] == "R2":
        categories.append("relevant_statute_retrieved_but_allocation_wrong")
    if case["retrieval_allocation_group"] == "R3":
        categories.append("relevant_statute_missing")
    if case["b0_allocation_exact"] and not case["b4_allocation_exact"]:
        categories.append("possible_retrieval_context_interference_transition")
    if not case["b4_predicted_total_matches_reference"]:
        categories.append("predicted_total_mismatch")
    if case["case_id"] == "109" and case["b4_invalid"] and has_duplicate_recipients(prediction):
        categories.append("multi_stage_succession_duplicate_recipient_representation")
    return categories


def load_eval(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return report, index_unique(report["cases"], str(path))


def require_same_cases(expected: set[str], **sources: dict[str, Any]) -> None:
    if set(CASE_ISSUES) != expected:
        raise ValueError("Frozen CASE_ISSUES does not match evaluation cases")
    for label, source in sources.items():
        if set(source) != expected:
            raise ValueError(f"{label} case IDs differ from the evaluation set")


def retrieval_configuration(trace: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "retrieval_method", "bm25_k1", "bm25_b", "bm25_candidate_k",
        "dense_model", "dense_metric", "dense_candidate_k",
        "dense_output_dimension", "rrf_k", "final_top_k", "query_source",
        "corpus_path", "corpus_sha256", "prompt_version", "model",
        "reasoning_effort", "max_output_tokens", "temperature",
    ]
    return {field: trace[field] for field in fields}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    b0_report, b0_eval = load_eval(args.b0_eval)
    b2_report, b2_eval = load_eval(args.b2_eval)
    b4_report, b4_eval = load_eval(args.b4_eval)
    b2_trace = index_unique(load_jsonl(args.b2_trace), str(args.b2_trace))
    b4_trace = index_unique(load_jsonl(args.b4_trace), str(args.b4_trace))
    b4_predictions = index_unique(load_jsonl(args.b4_predictions), str(args.b4_predictions))
    expected = set(b4_eval)
    require_same_cases(expected, b0_eval=b0_eval, b2_eval=b2_eval, b2_trace=b2_trace,
                       b4_trace=b4_trace, b4_predictions=b4_predictions)

    first_config = retrieval_configuration(next(iter(b4_trace.values())))
    for case_id, trace in b4_trace.items():
        if retrieval_configuration(trace) != first_config:
            raise ValueError(f"B4 retrieval configuration drift in case {case_id}")
        if len(trace.get("retrieved_statute_ids", [])) != first_config["final_top_k"]:
            raise ValueError(f"B4 case {case_id} has unexpected fused result length")

    cases: list[dict[str, Any]] = []
    for case_id in sorted(expected, key=int):
        annotation = CASE_ISSUES[case_id]
        relevant_ids = annotation["relevant_statutes"]
        b2_diag = retrieval_diagnostic(b2_trace[case_id]["retrieved_statute_ids"], relevant_ids)
        b4_diag = retrieval_diagnostic(b4_trace[case_id]["retrieved_statute_ids"], relevant_ids)
        b0_exact = bool(b0_eval[case_id]["allocation_exact"])
        b2_exact = bool(b2_eval[case_id]["allocation_exact"])
        b4_exact = bool(b4_eval[case_id]["allocation_exact"])
        row = {
            "case_id": case_id,
            "dominant_issues": annotation["issues"],
            "relevant_statute_ids": relevant_ids,
            "annotation_note": annotation.get("annotation_note"),
            "b2_retrieved_statute_ids": b2_trace[case_id]["retrieved_statute_ids"],
            "b4_bm25_candidate_ids": b4_trace[case_id]["bm25_statute_ids"],
            "b4_dense_candidate_ids": b4_trace[case_id]["dense_statute_ids"],
            "b4_retrieved_statute_ids": b4_trace[case_id]["retrieved_statute_ids"],
            "b2_issue_relevant_in_top5": b2_diag["issue_relevant_in_top5"],
            "b2_number_relevant_in_top5": b2_diag["number_relevant_in_top5"],
            "b4_issue_relevant_in_top5": b4_diag["issue_relevant_in_top5"],
            "b4_number_relevant_in_top5": b4_diag["number_relevant_in_top5"],
            "b4_relevant_retrieved_ids": b4_diag["relevant_retrieved_ids"],
            "b4_relevant_rank": b4_diag["relevant_rank"],
            "retrieval_transition": retrieval_transition(
                b2_diag["issue_relevant_in_top5"], b4_diag["issue_relevant_in_top5"]),
            "b0_allocation_exact": b0_exact,
            "b2_allocation_exact": b2_exact,
            "b4_allocation_exact": b4_exact,
            "end_to_end_transition": end_to_end_transition(b0_exact, b2_exact, b4_exact),
            "retrieval_allocation_group": retrieval_allocation_group(
                b4_diag["issue_relevant_in_top5"], b4_exact),
            "b4_heir_f1": b4_eval[case_id]["heir_f1"],
            "b4_amounts_correct": b4_eval[case_id].get("amounts_correct", 0),
            "reference_recipients": b4_eval[case_id].get("reference_recipients", 0),
            "b4_predicted_total_matches_reference": b4_eval[case_id].get(
                "predicted_total_matches_reference", False),
            "b4_invalid": bool(b4_eval[case_id].get("invalid", False)),
            "b4_validation_errors": b4_eval[case_id].get("validation_errors", []),
        }
        row["error_categories"] = case_error_categories(row, b4_predictions[case_id])
        cases.append(row)

    known = [row for row in cases if row["b4_issue_relevant_in_top5"] is not None]
    b2_relevance_hits = sum(row["b2_issue_relevant_in_top5"] for row in known)
    relevance_hits = sum(row["b4_issue_relevant_in_top5"] for row in known)
    b2_relevance_rate = b2_relevance_hits / len(known)
    b4_relevance_rate = relevance_hits / len(known)
    retrieval_counts = Counter(row["retrieval_transition"] for row in cases)
    e2e_counts = Counter(row["end_to_end_transition"] for row in cases)
    diagnostic_counts = Counter(row["retrieval_allocation_group"] for row in cases)
    taxonomy_cases: dict[str, list[str]] = {}
    for row in cases:
        for category in row["error_categories"]:
            taxonomy_cases.setdefault(category, []).append(row["case_id"])

    taxonomy_descriptions = {
        "wrong_heir_identification": "Predicted recipient set differs from the reference recipient set.",
        "wrong_monetary_allocation": "At least one reference-recipient amount is not exactly correct; categories may overlap.",
        "relevant_statute_retrieved_but_allocation_wrong": "Central statute is in fused top-5, but final allocation is not exact.",
        "relevant_statute_missing": "No annotated central statute is in fused top-5 and allocation is not exact.",
        "possible_retrieval_context_interference_transition": "B0 was exact and B4 was wrong; this is a transition observation, not causal proof.",
        "predicted_total_mismatch": "Predicted allocation total differs from the reference total.",
        "multi_stage_succession_duplicate_recipient_representation": "Multi-stage succession / duplicate recipient representation.",
    }
    taxonomy = []
    for category, case_ids in sorted(taxonomy_cases.items()):
        taxonomy.append({
            "category": category,
            "description": taxonomy_descriptions[category],
            "count": len(case_ids),
            "case_ids": case_ids,
            "status": "observed_in_development_n_1" if len(case_ids) == 1 else "recurring_pattern",
        })

    all_e2e_transitions = [
        end_to_end_transition(b0, b2, b4)
        for b0 in (False, True)
        for b2 in (False, True)
        for b4 in (False, True)
    ]
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "annotation_source": {
            "version": B2_ANNOTATION_VERSION,
            "policy": "Reuse frozen Task #004 annotations; unknown remains unknown.",
        },
        "dataset": {"split": "development", "cases": len(cases)},
        "sources": {key: str(value) for key, value in vars(args).items()},
        "b4_retrieval_configuration": first_config,
        "baseline_metrics": {
            "b0": b0_report["metrics"], "b2": b2_report["metrics"], "b4": b4_report["metrics"]},
        "annotation_coverage": {
            "known_cases": len(known), "total_cases": len(cases),
            "rate": len(known) / len(cases),
            "uncertain_case_ids": [row["case_id"] for row in cases if row["b4_issue_relevant_in_top5"] is None],
        },
        "b4_relevance_metrics": {
            "cases_with_relevant_statute_in_top5": relevance_hits,
            "issue_relevant_in_top5_rate": b4_relevance_rate,
            "mean_relevant_statutes_in_top5": sum(row["b4_number_relevant_in_top5"] for row in known) / len(known),
        },
        "b2_vs_b4_relevance_summary": {
            "known_cases": len(known),
            "b2_cases_with_relevant_statute_in_top5": b2_relevance_hits,
            "b2_issue_relevant_in_top5_rate": b2_relevance_rate,
            "b2_mean_relevant_statutes_in_top5": sum(row["b2_number_relevant_in_top5"] for row in known) / len(known),
            "b4_cases_with_relevant_statute_in_top5": relevance_hits,
            "b4_issue_relevant_in_top5_rate": b4_relevance_rate,
            "b4_mean_relevant_statutes_in_top5": sum(row["b4_number_relevant_in_top5"] for row in known) / len(known),
            "absolute_rate_delta_b4_minus_b2": b4_relevance_rate - b2_relevance_rate,
            "conclusion": "B4 did not improve central-statute top-5 coverage over B2 on the development set."
            if b4_relevance_rate <= b2_relevance_rate else
            "B4 improved central-statute top-5 coverage over B2 on the development set.",
        },
        "b2_vs_b4_retrieval_transitions": {
            key: {"count": retrieval_counts.get(key, 0), "percentage_all_cases": retrieval_counts.get(key, 0) / len(cases),
                  "percentage_known_cases": (retrieval_counts.get(key, 0) / len(known) if key != "retrieval_uncertain" else None),
                  "case_ids": [row["case_id"] for row in cases if row["retrieval_transition"] == key]}
            for key in ["retrieval_improved", "retrieval_regressed", "retrieval_both_relevant", "retrieval_both_missing", "retrieval_uncertain"]
        },
        "end_to_end_transitions": {
            key: {"count": e2e_counts.get(key, 0), "percentage": e2e_counts.get(key, 0) / len(cases),
                  "case_ids": [row["case_id"] for row in cases if row["end_to_end_transition"] == key]}
            for key in all_e2e_transitions
        },
        "retrieval_vs_allocation": {
            "groups": {
                key: {"count": diagnostic_counts.get(key, 0),
                      "case_ids": [row["case_id"] for row in cases if row["retrieval_allocation_group"] == key]}
                for key in ["R1", "R2", "R3", "R4", "RU_correct", "RU_wrong"]
            },
            "interpretation": {
                "R1": "Relevant statute retrieved and allocation exact.",
                "R2": "Relevant statute retrieved but allocation wrong; consistent with a downstream limitation.",
                "R3": "Relevant statute missing and allocation wrong; consistent with a retrieval limitation, but downstream error cannot be excluded.",
                "R4": "Relevant statute missing but allocation exact; diagnostic observation, not evidence that retrieval is unnecessary.",
                "RU": "Relevance annotation uncertain; excluded from relevance conclusions.",
            },
        },
        "error_taxonomy": taxonomy,
        "case_109": {
            "category": "Multi-stage succession / duplicate recipient representation",
            "status": "observed in development, n=1",
            "invalid": b4_eval["109"].get("invalid", False),
            "raw_prediction_modified": False,
            "duplicate_recipient_detected": has_duplicate_recipients(b4_predictions["109"]),
            "validation_errors": b4_eval["109"].get("validation_errors", []),
        },
        "cases": cases,
    }


def markdown_report(report: dict[str, Any]) -> str:
    ann = report["annotation_coverage"]
    rel = report["b4_relevance_metrics"]
    comparison = report["b2_vs_b4_relevance_summary"]
    lines = [
        "# B4 Retrieval Diagnostic and Transition Analysis", "",
        "## 1. Executive summary", "",
        f"B4 retrieved at least one annotated central statute for **{rel['cases_with_relevant_statute_in_top5']}/{ann['known_cases']}** confidently annotated cases ({rel['issue_relevant_in_top5_rate']:.2%}). "
        f"The mean was **{rel['mean_relevant_statutes_in_top5']:.3f}** relevant statutes per fused top-5.",
        f"B2 covered {comparison['b2_cases_with_relevant_statute_in_top5']}/{comparison['known_cases']} ({comparison['b2_issue_relevant_in_top5_rate']:.2%}); the B4−B2 absolute delta is {comparison['absolute_rate_delta_b4_minus_b2']:+.2%}. **{comparison['conclusion']}**",
        "This report is diagnostic evidence only: outcome transitions do not establish that retrieval caused an allocation result.", "",
        "## 2. B4 retrieval relevance", "",
        f"- Annotation coverage: {ann['known_cases']}/{ann['total_cases']} ({ann['rate']:.2%})",
        f"- Relevant central statute in top-5: {rel['cases_with_relevant_statute_in_top5']}/{ann['known_cases']} ({rel['issue_relevant_in_top5_rate']:.2%})",
        f"- Mean relevant statutes in top-5: {rel['mean_relevant_statutes_in_top5']:.3f}",
        f"- Uncertain cases retained as unknown: {', '.join(ann['uncertain_case_ids'])}", "",
        "## 3. B2 vs B4 retrieval comparison", "",
        f"B2: {comparison['b2_cases_with_relevant_statute_in_top5']}/{comparison['known_cases']} ({comparison['b2_issue_relevant_in_top5_rate']:.2%}); B4: {comparison['b4_cases_with_relevant_statute_in_top5']}/{comparison['known_cases']} ({comparison['b4_issue_relevant_in_top5_rate']:.2%}); delta: {comparison['absolute_rate_delta_b4_minus_b2']:+.2%}.", "",
        "| Transition | Count | % known | Cases |", "| --- | ---: | ---: | --- |",
    ]
    for key, item in report["b2_vs_b4_retrieval_transitions"].items():
        percent = "—" if item["percentage_known_cases"] is None else f"{item['percentage_known_cases']:.2%}"
        lines.append(f"| `{key}` | {item['count']} | {percent} | {', '.join(item['case_ids']) or '—'} |")
    lines += ["", "## 4. B0/B2/B4 transition analysis", "",
              "| Transition | Count | Cases |", "| --- | ---: | --- |"]
    for key, item in report["end_to_end_transitions"].items():
        lines.append(f"| `{key}` | {item['count']} | {', '.join(item['case_ids'])} |")
    lines += ["", "## 5. Retrieval vs downstream allocation", "",
              "| Group | Retrieval relevant? | Allocation correct? | Count | Cases | Interpretation |",
              "| --- | --- | --- | ---: | --- | --- |"]
    labels = {
        "R1": ("yes", "yes"), "R2": ("yes", "no"), "R3": ("no", "no"), "R4": ("no", "yes"),
        "RU_correct": ("unknown", "yes"), "RU_wrong": ("unknown", "no"),
    }
    for key, item in report["retrieval_vs_allocation"]["groups"].items():
        interpretation_key = "RU" if key.startswith("RU") else key
        lines.append(f"| {key} | {labels[key][0]} | {labels[key][1]} | {item['count']} | {', '.join(item['case_ids']) or '—'} | {report['retrieval_vs_allocation']['interpretation'][interpretation_key]} |")
    lines += ["", "Among failures, R2 is consistent with a downstream direct-allocation limitation after successful retrieval. R3 is consistent with a retrieval limitation, but the observational design cannot distinguish causally or exclude simultaneous downstream errors.", "",
              "## 6. Error taxonomy", "",
              "Categories overlap; counts must not be summed as mutually exclusive failures.", "",
              "| Category | Count | Status | Cases |", "| --- | ---: | --- | --- |"]
    for item in report["error_taxonomy"]:
        lines.append(f"| `{item['category']}` | {item['count']} | {item['status']} | {', '.join(item['case_ids'])} |")
    case109 = report["case_109"]
    lines += ["", "## 7. Case 109 analysis", "",
              f"Case 109 is classified as **{case109['category']}** ({case109['status']}).",
              "The model emitted the same final recipients in separate succession-stage rows. The evaluator correctly marked the case invalid rather than merging those rows. The raw prediction remains unchanged.", "",
              "## 8. Research interpretation", "",
              "The retrieval comparison measures whether fused top-5 contains at least one manually annotated central provision. When B4 retrieves a relevant provision but remains wrong, the result suggests that retrieval alone is insufficient for direct allocation. When both retrieval and allocation fail, the evidence is compatible with a retrieval bottleneck but cannot isolate it causally.", "",
              "## 9. Limitations", "",
              "- Only 30 development cases are analyzed; no held-out claim is made.",
              "- Relevance is binary top-5 coverage of central provisions, not graded passage utility.",
              "- Two historical/mixed-regime cases remain unknown and are excluded from relevance rates.",
              "- Transition and interference labels are observational, not causal.",
              "- Error categories overlap and use evaluator-level symptoms rather than independent legal adjudication.", "",
              "## 10. Recommended next research step", "",
              "Freeze this B4 diagnostic, then implement the pre-specified B5 coordinated modular baseline without tuning B4 or using these case-level outcomes as retrieval rules.", "",
              "## Case-level diagnostic", "",
              "| Case | B2 rel. | B4 rel. | Retrieval transition | B0/B2/B4 exact | R-group | Errors |",
              "| --- | ---: | ---: | --- | --- | --- | --- |"]
    for row in report["cases"]:
        b2rel = "?" if row["b2_issue_relevant_in_top5"] is None else row["b2_issue_relevant_in_top5"]
        b4rel = "?" if row["b4_issue_relevant_in_top5"] is None else row["b4_issue_relevant_in_top5"]
        exact = f"{int(row['b0_allocation_exact'])}/{int(row['b2_allocation_exact'])}/{int(row['b4_allocation_exact'])}"
        lines.append(f"| {row['case_id']} | {b2rel} | {b4rel} | `{row['retrieval_transition']}` | {exact} | {row['retrieval_allocation_group']} | {', '.join(row['error_categories']) or '—'} |")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {
        "b0_eval": ROOT / "data/eval/allocation_dev_b0.json",
        "b2_eval": ROOT / "data/eval/allocation_dev_b2.json",
        "b4_eval": ROOT / "data/eval/allocation_dev_b4.json",
        "b2_trace": ROOT / "data/runs/allocation_dev_b2.trace.jsonl",
        "b4_trace": ROOT / "data/runs/allocation_dev_b4.trace.jsonl",
        "b4_predictions": ROOT / "data/runs/allocation_dev_b4.jsonl",
        "output_json": ROOT / "data/eval/b4_retrieval_diagnostic.json",
        "output_md": ROOT / "data/eval/b4_retrieval_diagnostic.md",
    }
    for key, value in defaults.items():
        parser.add_argument("--" + key.replace("_", "-"), type=Path, default=value)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(markdown_report(report), encoding="utf-8")
    print(f"Analyzed {report['dataset']['cases']} B4 development cases offline.")
    metrics = report["b4_relevance_metrics"]
    print(f"B4 relevant central statute in top-5: {metrics['issue_relevant_in_top5_rate']:.4f}")
    print(f"Mean relevant statutes in top-5: {metrics['mean_relevant_statutes_in_top5']:.4f}")
    print(f"JSON report: {args.output_json}")
    print(f"Markdown report: {args.output_md}")


if __name__ == "__main__":
    main()
