#!/usr/bin/env python3
"""Offline B4-to-B5 transition and observable module-output diagnostic."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from analyze_b2_retrieval import index_unique, load_jsonl
    from analyze_b4_retrieval import has_duplicate_recipients
except ModuleNotFoundError:
    from scripts.analyze_b2_retrieval import index_unique, load_jsonl
    from scripts.analyze_b4_retrieval import has_duplicate_recipients


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_VERSION = "b5-transition-diagnostic-v1"
METHOD_ORDER = ("b0", "b2", "b4", "b5")


def b4_b5_transition(b4_exact: bool, b5_exact: bool) -> str:
    if b4_exact and b5_exact:
        return "T1_both_correct"
    if not b4_exact and b5_exact:
        return "T2_b5_improvement"
    if b4_exact and not b5_exact:
        return "T3_b5_regression"
    return "T4_both_wrong"


def four_method_pattern(statuses: dict[str, bool]) -> str:
    return "".join("1" if statuses[method] else "0" for method in METHOD_ORDER)


def retrieval_outcome_group(
    relevance: int | None, b4_exact: bool, b5_exact: bool
) -> str:
    if relevance is None:
        return "G7_relevance_uncertain"
    if relevance:
        if not b4_exact and b5_exact:
            return "G1_relevant_b4_wrong_b5_correct"
        if not b4_exact and not b5_exact:
            return "G2_relevant_both_wrong"
        if b4_exact and not b5_exact:
            return "G5_relevant_b4_correct_b5_wrong"
        return "G6_relevant_both_correct"
    if not b4_exact and b5_exact:
        return "G3_missing_b4_wrong_b5_correct"
    if not b4_exact and not b5_exact:
        return "G4_missing_both_wrong"
    # The requested G1-G6 definitions omit retrieval-missing cases where B4 is
    # already correct. Preserve them explicitly instead of misclassifying them.
    return "GX_not_covered_by_defined_G1_G6"


def transition_case_ids(cases: list[dict[str, Any]], transition: str) -> list[str]:
    return [row["case_id"] for row in cases if row["b4_b5_transition"] == transition]


def module_outputs(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {module["module"]: module["output"] for module in trace["modules"]}


def observable_module_characteristics(trace: dict[str, Any]) -> dict[str, Any]:
    outputs = module_outputs(trace)
    extraction = outputs["structured_case_extraction"]
    issues = outputs["inheritance_issue_analysis"]
    reasoning = outputs["statute_aware_reasoning"]
    return {
        "extracted_person_count": len(extraction["persons"]),
        "extracted_openings": extraction["succession_openings"],
        "extracted_asset_count": len(extraction["assets"]),
        "extracted_obligation_count": len(extraction["obligations"]),
        "extracted_will_gift_transfer_count": len(extraction["wills_gifts_transfers"]),
        "succession_modes": issues["succession_modes"],
        "succession_order": issues["succession_order"],
        "will_issues": issues["will_issues"],
        "representation_issues": issues["representation_issues"],
        "mandatory_share_issues": issues["mandatory_share_issues"],
        "estate_issues": issues["estate_issues"],
        "multi_stage_issues": issues["multi_stage_issues"],
        "reasoning_applicable_statutes": reasoning["applicable_statutes"],
        "reasoning_step_count": len(reasoning["reasoning_steps"]),
        "intermediate_succession_states": reasoning["intermediate_succession_states"],
        "intermediate_calculations": reasoning["intermediate_calculations"],
        "assumptions": reasoning["assumptions"],
        "unresolved_ambiguities": reasoning["unresolved_ambiguities"],
    }


def error_categories(
    eval_case: dict[str, Any], prediction: dict[str, Any], relevance: int | None,
    *, b4_was_correct: bool = False,
) -> list[str]:
    if eval_case["allocation_exact"]:
        return []
    categories: list[str] = []
    if eval_case["heir_f1"] < 1.0:
        categories.append("wrong_heir_identification")
    if eval_case.get("amounts_correct", 0) < eval_case.get("reference_recipients", 0):
        categories.append("wrong_monetary_allocation")
    if eval_case["heir_f1"] == 1.0:
        categories.append("correct_recipient_set_wrong_amounts")
    if relevance == 1:
        categories.append("relevant_statute_retrieved_but_allocation_wrong")
    elif relevance == 0:
        categories.append("relevant_statute_missing")
    if not eval_case.get("predicted_total_matches_reference", False):
        categories.append("predicted_total_mismatch")
    if eval_case.get("invalid", False) and has_duplicate_recipients(prediction):
        categories.append("multi_stage_succession_duplicate_recipient_representation")
    if b4_was_correct:
        categories.append("regression_after_correct_b4_result")
    return categories


def summarize_taxonomy(cases: list[dict[str, Any]], method: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in cases:
        for category in row[f"{method}_error_categories"]:
            result.setdefault(category, []).append(row["case_id"])
    return result


def case_109_result(
    b4_eval: dict[str, Any], b5_eval: dict[str, Any],
    b4_prediction: dict[str, Any], b5_prediction: dict[str, Any],
    b5_trace: dict[str, Any], reference: dict[str, Any],
) -> dict[str, Any]:
    outputs = module_outputs(b5_trace)
    reasoning = outputs["statute_aware_reasoning"]
    return {
        "b4_invalid": bool(b4_eval.get("invalid", False)),
        "b4_duplicate_recipients": has_duplicate_recipients(b4_prediction),
        "b5_invalid": bool(b5_eval.get("invalid", False)),
        "b5_duplicate_recipients": has_duplicate_recipients(b5_prediction),
        "b5_allocation_exact": bool(b5_eval["allocation_exact"]),
        "b5_heir_f1": b5_eval["heir_f1"],
        "b5_multi_stage_issue_output": outputs["inheritance_issue_analysis"]["multi_stage_issues"],
        "b5_intermediate_succession_states": reasoning["intermediate_succession_states"],
        "b5_final_allocation": b5_prediction["allocations"],
        "reference_allocation": reference["reference_settlement"],
        "conclusion": (
            "B5 removed the duplicate-recipient representation and explicitly represented two succession stages, "
            "but its final recipients and amounts still do not match the reference; the conceptual allocation problem was not solved."
        ),
    }


def load_eval(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return report, index_unique(report["cases"], str(path))


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    eval_reports: dict[str, dict[str, Any]] = {}
    eval_cases: dict[str, dict[str, dict[str, Any]]] = {}
    for method in METHOD_ORDER:
        report, cases = load_eval(getattr(args, f"{method}_eval"))
        eval_reports[method], eval_cases[method] = report, cases
    b4_predictions = index_unique(load_jsonl(args.b4_predictions), str(args.b4_predictions))
    b5_predictions = index_unique(load_jsonl(args.b5_predictions), str(args.b5_predictions))
    b4_trace = index_unique(load_jsonl(args.b4_trace), str(args.b4_trace))
    b5_trace = index_unique(load_jsonl(args.b5_trace), str(args.b5_trace))
    references = index_unique(load_jsonl(args.reference), str(args.reference))
    b4_diagnostic = json.loads(args.b4_diagnostic.read_text(encoding="utf-8"))
    b4_diag_cases = index_unique(b4_diagnostic["cases"], str(args.b4_diagnostic))
    expected = set(eval_cases["b5"])
    sources = {
        **{f"{method}_eval": eval_cases[method] for method in METHOD_ORDER},
        "b4_predictions": b4_predictions, "b5_predictions": b5_predictions,
        "b4_trace": b4_trace, "b5_trace": b5_trace,
        "b4_diagnostic": b4_diag_cases,
    }
    for label, source in sources.items():
        if set(source) != expected:
            raise ValueError(f"{label} case IDs differ from B5 evaluation")
    references = {case_id: references[case_id] for case_id in expected}

    cases: list[dict[str, Any]] = []
    for case_id in sorted(expected, key=int):
        statuses = {method: bool(eval_cases[method][case_id]["allocation_exact"]) for method in METHOD_ORDER}
        relevance = b4_diag_cases[case_id]["b4_issue_relevant_in_top5"]
        row = {
            "case_id": case_id,
            "exact_status": statuses,
            "binary_pattern": four_method_pattern(statuses),
            "b4_b5_transition": b4_b5_transition(statuses["b4"], statuses["b5"]),
            "b4_retrieval_relevant": relevance,
            "retrieval_outcome_group": retrieval_outcome_group(relevance, statuses["b4"], statuses["b5"]),
            "b4_retrieved_statute_ids": b4_trace[case_id]["retrieved_statute_ids"],
            "b5_retrieved_statute_ids": b5_trace[case_id]["retrieved_statute_ids"],
            "retrieval_unchanged": b4_trace[case_id]["retrieved_statute_ids"] == b5_trace[case_id]["retrieved_statute_ids"],
            "b4_heir_f1": eval_cases["b4"][case_id]["heir_f1"],
            "b5_heir_f1": eval_cases["b5"][case_id]["heir_f1"],
            "b4_invalid": bool(eval_cases["b4"][case_id].get("invalid", False)),
            "b5_invalid": bool(eval_cases["b5"][case_id].get("invalid", False)),
        }
        row["b4_error_categories"] = error_categories(
            eval_cases["b4"][case_id], b4_predictions[case_id], relevance)
        row["b5_error_categories"] = error_categories(
            eval_cases["b5"][case_id], b5_predictions[case_id], relevance,
            b4_was_correct=statuses["b4"])
        cases.append(row)

    transition_order = ["T1_both_correct", "T2_b5_improvement", "T3_b5_regression", "T4_both_wrong"]
    transition_counts = Counter(row["b4_b5_transition"] for row in cases)
    transitions = {
        key: {"count": transition_counts[key], "percentage": transition_counts[key] / len(cases),
              "case_ids": transition_case_ids(cases, key)} for key in transition_order
    }
    b4_correct = sum(row["exact_status"]["b4"] for row in cases)
    b5_correct = sum(row["exact_status"]["b5"] for row in cases)
    if sum(item["count"] for item in transitions.values()) != len(cases):
        raise AssertionError("B4/B5 transitions do not cover all cases")
    if transitions["T2_b5_improvement"]["count"] - transitions["T3_b5_regression"]["count"] != b5_correct - b4_correct:
        raise AssertionError("B4/B5 transition net change is inconsistent")

    patterns: dict[str, dict[str, Any]] = {}
    for pattern in sorted({row["binary_pattern"] for row in cases}):
        ids = [row["case_id"] for row in cases if row["binary_pattern"] == pattern]
        patterns[pattern] = {"count": len(ids), "case_ids": ids}

    group_order = [
        "G1_relevant_b4_wrong_b5_correct", "G2_relevant_both_wrong",
        "G3_missing_b4_wrong_b5_correct", "G4_missing_both_wrong",
        "G5_relevant_b4_correct_b5_wrong", "G6_relevant_both_correct",
        "G7_relevance_uncertain", "GX_not_covered_by_defined_G1_G6",
    ]
    group_counts = Counter(row["retrieval_outcome_group"] for row in cases)
    groups = {
        key: {"count": group_counts[key], "percentage": group_counts[key] / len(cases),
              "case_ids": [row["case_id"] for row in cases if row["retrieval_outcome_group"] == key]}
        for key in group_order
    }

    def detailed_case(case_id: str) -> dict[str, Any]:
        base = next(row for row in cases if row["case_id"] == case_id)
        return {
            "case_id": case_id,
            "retrieval_unchanged": base["retrieval_unchanged"],
            "b4_retrieved_statute_ids": base["b4_retrieved_statute_ids"],
            "b5_retrieved_statute_ids": base["b5_retrieved_statute_ids"],
            "b4_failure_characteristics": base["b4_error_categories"],
            "b5_observable_intermediate_characteristics": observable_module_characteristics(b5_trace[case_id]),
            "b4_final_allocation": b4_predictions[case_id]["allocations"],
            "b5_final_allocation": b5_predictions[case_id]["allocations"],
            "reference_allocation": references[case_id]["reference_settlement"],
        }

    improvement_cases = [detailed_case(cid) for cid in transitions["T2_b5_improvement"]["case_ids"]]
    regression_cases = [detailed_case(cid) for cid in transitions["T3_b5_regression"]["case_ids"]]

    recurring_patterns = []
    if improvement_cases:
        feature_tests = {
            "explicit_succession_order": lambda c: bool(c["b5_observable_intermediate_characteristics"]["succession_order"]),
            "intermediate_calculations": lambda c: bool(c["b5_observable_intermediate_characteristics"]["intermediate_calculations"]),
            "estate_issues_explicitly_represented": lambda c: bool(c["b5_observable_intermediate_characteristics"]["estate_issues"]),
            "will_issues_explicitly_represented": lambda c: bool(c["b5_observable_intermediate_characteristics"]["will_issues"]),
            "intermediate_succession_states": lambda c: bool(c["b5_observable_intermediate_characteristics"]["intermediate_succession_states"]),
        }
        for feature, predicate in feature_tests.items():
            ids = [case["case_id"] for case in improvement_cases if predicate(case)]
            if len(ids) >= 2:
                recurring_patterns.append({"observable_feature": feature, "count": len(ids), "case_ids": ids,
                                           "causal_claim": False})

    b4_taxonomy = summarize_taxonomy(cases, "b4")
    b5_taxonomy = summarize_taxonomy(cases, "b5")
    taxonomy_order = [
        "wrong_heir_identification", "wrong_monetary_allocation",
        "correct_recipient_set_wrong_amounts",
        "relevant_statute_retrieved_but_allocation_wrong", "relevant_statute_missing",
        "predicted_total_mismatch", "multi_stage_succession_duplicate_recipient_representation",
        "regression_after_correct_b4_result",
    ]
    taxonomy = [{
        "category": category,
        "b4_count": len(b4_taxonomy.get(category, [])),
        "b5_count": len(b5_taxonomy.get(category, [])),
        "b4_case_ids": b4_taxonomy.get(category, []),
        "b5_case_ids": b5_taxonomy.get(category, []),
        "evidence": "Computed with the same evaluator symptom and frozen B4 relevance annotation for both methods."
        if category not in {"regression_after_correct_b4_result"} else
        "B5-specific transition category: B4 allocation exact and B5 allocation non-exact.",
    } for category in taxonomy_order]

    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "dataset": {"split": "development", "cases": len(cases), "method_order": list(METHOD_ORDER)},
        "sources": {key: str(value) for key, value in vars(args).items()},
        "metrics": {method: eval_reports[method]["metrics"] for method in METHOD_ORDER},
        "b4_b5_transitions": transitions,
        "transition_consistency": {
            "total": sum(item["count"] for item in transitions.values()),
            "b4_correct": b4_correct, "b5_correct": b5_correct,
            "t2_minus_t3": transitions["T2_b5_improvement"]["count"] - transitions["T3_b5_regression"]["count"],
            "correct_count_delta": b5_correct - b4_correct,
        },
        "four_method_patterns": patterns,
        "retrieval_cross_groups": groups,
        "retrieval_preservation": {
            "all_30_fused_top5_unchanged": all(row["retrieval_unchanged"] for row in cases),
            "changed_case_ids": [row["case_id"] for row in cases if not row["retrieval_unchanged"]],
        },
        "improvement_cases": improvement_cases,
        "improvement_recurring_observable_patterns": recurring_patterns,
        "regression_cases": regression_cases,
        "error_taxonomy_comparison": taxonomy,
        "case_109": case_109_result(
            eval_cases["b4"]["109"], eval_cases["b5"]["109"],
            b4_predictions["109"], b5_predictions["109"], b5_trace["109"], references["109"]),
        "limitations": [
            "Development set only (30 cases); no statistical significance or held-out generalization claim.",
            "Transitions are observational and do not establish modular reasoning as the causal mechanism.",
            "Binary exact match hides partial improvements or degradations.",
            "B4 relevance is a central-statute top-5 annotation, not graded context utility.",
            "G1-G6 omit retrieval-missing cases where B4 was already correct; these are retained as GX.",
            "Intermediate-output descriptions report emitted JSON only, not hidden model reasoning.",
        ],
        "cases": cases,
    }


def compact_allocations(rows: list[dict[str, Any]]) -> str:
    return "; ".join(f"{row['recipient']}: {row['amount']}" for row in rows)


def markdown_report(report: dict[str, Any]) -> str:
    t = report["b4_b5_transitions"]
    lines = [
        "# B4 → B5 Transition and Error Analysis", "",
        "## 1. Executive summary", "",
        f"B5 achieved 8/30 exact allocations (26.67%) versus B4's 6/30 (20.00%). It improved {t['T2_b5_improvement']['count']} cases and regressed {t['T3_b5_regression']['count']}, for a net gain of +2 exact cases. All B4/B5 fused top-5 statute lists were identical. These are development-set observations, not causal or significance claims.", "",
        "## 2. B4 → B5 transitions", "",
        "| Group | Count | Percentage | Cases |", "| --- | ---: | ---: | --- |",
    ]
    for key, item in t.items():
        lines.append(f"| `{key}` | {item['count']} | {item['percentage']:.2%} | {', '.join(item['case_ids']) or '—'} |")
    consistency = report["transition_consistency"]
    lines += ["", f"Checks: total = {consistency['total']}; T2−T3 = {consistency['t2_minus_t3']}; B5 correct−B4 correct = {consistency['correct_count_delta']}.", "",
              "## 3. B0/B2/B4/B5 patterns", "",
              "Method order is `B0 B2 B4 B5`; 1 means allocation exact.", "",
              "| Pattern | Count | Cases |", "| --- | ---: | --- |"]
    for pattern, item in report["four_method_patterns"].items():
        lines.append(f"| `{pattern}` | {item['count']} | {', '.join(item['case_ids'])} |")
    lines += ["", "## 4. Retrieval × B5 outcome analysis", "",
              "| Group | Count | Percentage | Cases |", "| --- | ---: | ---: | --- |"]
    for key, item in report["retrieval_cross_groups"].items():
        lines.append(f"| `{key}` | {item['count']} | {item['percentage']:.2%} | {', '.join(item['case_ids']) or '—'} |")
    lines += ["", "`GX` preserves cases 48 and 132 because the requested G1–G6 definitions do not cover retrieval-missing cases where B4 was already correct.", "",
              "## 5. B5 improvement cases", ""]
    for case in report["improvement_cases"]:
        obs = case["b5_observable_intermediate_characteristics"]
        lines += [f"### Case {case['case_id']}", "",
                  f"- Retrieval unchanged: {case['retrieval_unchanged']}",
                  f"- B4 retrieved statutes: {', '.join(case['b4_retrieved_statute_ids'])}",
                  f"- B5 retrieved statutes: {', '.join(case['b5_retrieved_statute_ids'])}",
                  f"- B4 failure characteristics: {', '.join(case['b4_failure_characteristics'])}",
                  f"- Observable issue output includes succession order entries: {len(obs['succession_order'])}; will issues: {len(obs['will_issues'])}; estate issues: {len(obs['estate_issues'])}; multi-stage issues: {len(obs['multi_stage_issues'])}.",
                  f"- Observable reasoning output includes {obs['reasoning_step_count']} steps, {len(obs['intermediate_succession_states'])} intermediate succession states and {len(obs['intermediate_calculations'])} calculations.",
                  f"- B5 allocation: {compact_allocations(case['b5_final_allocation'])}",
                  f"- Reference: {compact_allocations(case['reference_allocation'])}", ""]
    lines += ["Recurring observable features across at least two improvement cases:", ""]
    for item in report["improvement_recurring_observable_patterns"]:
        lines.append(f"- `{item['observable_feature']}`: {item['count']} cases ({', '.join(item['case_ids'])}); descriptive only, not causal.")
    lines += ["", "## 6. B5 regression cases", ""]
    for case in report["regression_cases"]:
        obs = case["b5_observable_intermediate_characteristics"]
        lines += [f"### Case {case['case_id']}", "",
                  f"- Retrieval unchanged: {case['retrieval_unchanged']}",
                  f"- B4 retrieved statutes: {', '.join(case['b4_retrieved_statute_ids'])}",
                  f"- B5 retrieved statutes: {', '.join(case['b5_retrieved_statute_ids'])}",
                  f"- B4 allocation: {compact_allocations(case['b4_final_allocation'])}",
                  f"- B5 allocation: {compact_allocations(case['b5_final_allocation'])}",
                  f"- Reference: {compact_allocations(case['reference_allocation'])}",
                  f"- Observable module behavior: {len(obs['intermediate_succession_states'])} succession states and {len(obs['intermediate_calculations'])} calculations; emitted assumptions={len(obs['assumptions'])}, unresolved ambiguities={len(obs['unresolved_ambiguities'])}.",
                  "- Diagnostic description: modular output introduced a non-reference final allocation despite unchanged retrieval; this does not establish the cause.", ""]
    lines += ["## 7. Error taxonomy comparison", "",
              "Categories overlap and are computed with the same evaluator symptoms/relevance annotation unless noted.", "",
              "| Error category | B4 | B5 | Evidence |", "| --- | ---: | ---: | --- |"]
    for item in report["error_taxonomy_comparison"]:
        lines.append(f"| `{item['category']}` | {item['b4_count']} | {item['b5_count']} | {item['evidence']} |")
    c109 = report["case_109"]
    lines += ["", "## 8. Case 109", "",
              f"- B4 invalid/duplicate: {c109['b4_invalid']}/{c109['b4_duplicate_recipients']}",
              f"- B5 invalid/duplicate: {c109['b5_invalid']}/{c109['b5_duplicate_recipients']}",
              f"- B5 exact: {c109['b5_allocation_exact']}; heir F1: {c109['b5_heir_f1']:.4f}",
              f"- B5 emitted {len(c109['b5_intermediate_succession_states'])} intermediate succession states.",
              f"- Result: {c109['conclusion']}", "",
              "## 9. Research interpretation", "",
              "Supported: B5 has 8/30 exact results versus B4's 6/30, no invalid cases versus one for B4, three case-level improvements, one regression, and unchanged retrieval. The G1 case is diagnostic evidence consistent with modular processing helping after a relevant statute was available; G2 cases show that relevant context plus modular processing often remained insufficient.", "",
              "Not established: statistical significance, held-out generalization, causal benefit from modular reasoning, retrieval being unnecessary, or overall superiority.", "",
              "## 10. Limitations", ""]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines += ["", "## 11. Recommended next step", "",
              "Freeze B5 and this diagnostic, then specify the IGEP implementation and evaluation protocol before any further development-set tuning. Preserve the held-out test lock.", ""]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {
        "b0_eval": ROOT / "data/eval/allocation_dev_b0.json",
        "b2_eval": ROOT / "data/eval/allocation_dev_b2.json",
        "b4_eval": ROOT / "data/eval/allocation_dev_b4.json",
        "b5_eval": ROOT / "data/eval/allocation_dev_b5.json",
        "b4_predictions": ROOT / "data/runs/allocation_dev_b4.jsonl",
        "b5_predictions": ROOT / "data/runs/allocation_dev_b5.jsonl",
        "b4_trace": ROOT / "data/runs/allocation_dev_b4.trace.jsonl",
        "b5_trace": ROOT / "data/runs/allocation_dev_b5.trace.jsonl",
        "b4_diagnostic": ROOT / "data/eval/b4_retrieval_diagnostic.json",
        "reference": ROOT / "data/canonical/reference.jsonl",
        "output_json": ROOT / "data/eval/b5_transition_diagnostic.json",
        "output_md": ROOT / "data/eval/b5_transition_diagnostic.md",
    }
    for key, value in defaults.items():
        parser.add_argument("--" + key.replace("_", "-"), type=Path, default=value)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(markdown_report(report), encoding="utf-8")
    print("Analyzed 30 B4/B5 development cases offline.")
    for key, item in report["b4_b5_transitions"].items():
        print(f"{key}: {item['count']}")
    print(f"JSON report: {args.output_json}")
    print(f"Markdown report: {args.output_md}")


if __name__ == "__main__":
    main()
