#!/usr/bin/env python3
"""Deterministic retrieval diagnostic for the frozen B2 development run.

This script reads completed experiment artifacts only.  It never imports the
runner, retrieves statutes, or calls a model/API.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_VERSION = "b2-retrieval-diagnostic-v1"


# Manually reviewed against the development facts and the versioned statute
# corpus. These are central issue provisions, not every provision that might be
# cited in a complete judgment. None means that the available historical-law
# materials do not support a confident article-level relevance judgment.
CASE_ISSUES: dict[str, dict[str, Any]] = {
    "1": {"issues": ["pre_1990_testamentary_succession"], "relevant_statutes": None,
          "annotation_note": "Opening in 1987 requires a composite historical-law analysis not represented by one confidently applicable article set."},
    "13": {"issues": ["simultaneous_death", "lapsed_testamentary_disposition"], "relevant_statutes": ["VN_BLDS_2005_ART_641", "VN_BLDS_2005_ART_667", "VN_BLDS_2005_ART_675"]},
    "15": {"issues": ["estate_obligations", "worship_estate", "legacy"], "relevant_statutes": ["VN_BLDS_2015_ART_615", "VN_BLDS_2015_ART_645", "VN_BLDS_2015_ART_646", "VN_BLDS_2015_ART_658"]},
    "16": {"issues": ["late_discovered_estate_obligation", "mandatory_heir"], "relevant_statutes": ["VN_BLDS_2015_ART_615", "VN_BLDS_2015_ART_644", "VN_BLDS_2015_ART_645"]},
    "20": {"issues": ["oral_will_validity"], "relevant_statutes": ["VN_BLDS_2015_ART_629", "VN_BLDS_2015_ART_630"]},
    "21": {"issues": ["oral_will_validity"], "relevant_statutes": ["VN_BLDS_2015_ART_629", "VN_BLDS_2015_ART_630"]},
    "22": {"issues": ["oral_will_validity"], "relevant_statutes": ["VN_BLDS_2015_ART_629", "VN_BLDS_2015_ART_630"]},
    "27": {"issues": ["intestate_first_rank_heirs", "nonmarital_child_inheritance"], "relevant_statutes": ["VN_BLDS_2015_ART_650", "VN_BLDS_2015_ART_651"]},
    "29": {"issues": ["mandatory_heir_share"], "relevant_statutes": ["VN_BLDS_2015_ART_644"]},
    "48": {"issues": ["heir_survives_opening_then_dies"], "relevant_statutes": ["VN_BLDS_2015_ART_613"]},
    "50": {"issues": ["oral_will_validity"], "relevant_statutes": ["VN_BLDS_2015_ART_629", "VN_BLDS_2015_ART_630"]},
    "57": {"issues": ["intestate_succession", "transfer_of_inheritance_shares"], "relevant_statutes": ["VN_BLDS_2015_ART_651", "VN_BLDS_2015_ART_660"]},
    "65": {"issues": ["sequential_intestate_succession_across_regimes"], "relevant_statutes": ["VN_BLDS_1995_ART_679", "VN_BLDS_2005_ART_676"]},
    "77": {"issues": ["testamentary_disposition", "partial_intestacy"], "relevant_statutes": ["VN_BLDS_2005_ART_655", "VN_BLDS_2005_ART_658", "VN_BLDS_2005_ART_676"]},
    "78": {"issues": ["sequential_intestate_succession", "estate_distribution"], "relevant_statutes": ["VN_BLDS_2005_ART_636", "VN_BLDS_2005_ART_676", "VN_BLDS_2015_ART_614", "VN_BLDS_2015_ART_651", "VN_BLDS_2015_ART_660"]},
    "83": {"issues": ["multiple_openings", "renunciation", "intestate_succession"], "relevant_statutes": ["VN_BLDS_2005_ART_676", "VN_BLDS_2015_ART_620", "VN_BLDS_2015_ART_651", "VN_BLDS_2015_ART_660"]},
    "84": {"issues": ["estate_obligations", "intestate_succession"], "relevant_statutes": ["VN_BLDS_2015_ART_615", "VN_BLDS_2015_ART_651"]},
    "85": {"issues": ["renunciation_or_share_transfer", "intestate_succession"], "relevant_statutes": ["VN_BLDS_2015_ART_620", "VN_BLDS_2015_ART_651", "VN_BLDS_2015_ART_660"]},
    "91": {"issues": ["mixed_pre_1990_and_later_openings"], "relevant_statutes": None,
           "annotation_note": "One estate opened in 1978 and the case combines historical and later regimes; a central article set is not confidently defined from the current corpus alone."},
    "104": {"issues": ["intestate_succession", "transfer_of_inheritance_shares"], "relevant_statutes": ["VN_BLDS_2005_ART_676", "VN_BLDS_2005_ART_685"]},
    "105": {"issues": ["representation"], "relevant_statutes": ["VN_BLDS_2005_ART_677"]},
    "109": {"issues": ["sequential_intestate_succession_across_regimes"], "relevant_statutes": ["VN_BLDS_2005_ART_676", "VN_BLDS_2015_ART_651"]},
    "110": {"issues": ["sequential_intestate_succession", "estate_distribution"], "relevant_statutes": ["VN_BLDS_2015_ART_651", "VN_BLDS_2015_ART_660"]},
    "116": {"issues": ["intestate_succession", "inheritance_share_agreement"], "relevant_statutes": ["VN_PLTK_1990_ART_25", "VN_PLTK_1990_ART_35"]},
    "118": {"issues": ["estate_scope", "intestate_succession"], "relevant_statutes": ["VN_BLDS_2015_ART_612", "VN_BLDS_2015_ART_651"]},
    "121": {"issues": ["heir_dies_after_opening", "transfer_of_inheritance_shares"], "relevant_statutes": ["VN_BLDS_2015_ART_651", "VN_BLDS_2015_ART_660"]},
    "131": {"issues": ["representation"], "relevant_statutes": ["VN_BLDS_2015_ART_652"]},
    "132": {"issues": ["testamentary_dispositions", "estate_manager_obligations", "legacy"], "relevant_statutes": ["VN_BLDS_2005_ART_631", "VN_BLDS_2005_ART_638", "VN_BLDS_2005_ART_639", "VN_BLDS_2005_ART_640", "VN_BLDS_2005_ART_645", "VN_BLDS_2015_ART_609", "VN_BLDS_2015_ART_616", "VN_BLDS_2015_ART_617", "VN_BLDS_2015_ART_618", "VN_BLDS_2015_ART_623"]},
    "133": {"issues": ["intestate_succession", "estate_distribution"], "relevant_statutes": ["VN_BLDS_1995_ART_677", "VN_BLDS_1995_ART_678", "VN_BLDS_1995_ART_679", "VN_BLDS_1995_ART_688"]},
    "141": {"issues": ["estate_scope", "intestate_succession"], "relevant_statutes": ["VN_BLDS_2005_ART_634", "VN_BLDS_2005_ART_635", "VN_BLDS_2005_ART_674", "VN_BLDS_2005_ART_675", "VN_BLDS_2005_ART_676"]},
}


def retrieval_diagnostic(retrieved: list[str], relevant: list[str] | None) -> dict[str, Any]:
    """Calculate issue coverage and best one-based rank."""
    if relevant is None:
        return {"issue_relevant_in_top5": None, "number_relevant_in_top5": None,
                "relevant_retrieved_ids": [], "relevant_rank": None}
    relevant_set = set(relevant)
    hits = [statute_id for statute_id in retrieved[:5] if statute_id in relevant_set]
    ranks = [index for index, statute_id in enumerate(retrieved[:5], 1) if statute_id in relevant_set]
    return {"issue_relevant_in_top5": int(bool(hits)), "number_relevant_in_top5": len(hits),
            "relevant_retrieved_ids": hits, "relevant_rank": min(ranks) if ranks else None}


def transition_group(b0_exact: bool, b2_exact: bool, relevance: int | None) -> str:
    """Return the paired outcome group; U denotes unknown relevance."""
    if not b0_exact and b2_exact:
        return "A"
    if not b0_exact and not b2_exact:
        return "B" if relevance == 1 else "C" if relevance == 0 else "U"
    if b0_exact and not b2_exact:
        return "D"
    return "E"


def aggregate_relevance(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate retrieval relevance, excluding unknown annotations."""
    known = [row for row in cases if row["issue_relevant_in_top5"] is not None]
    if not known:
        return {"cases_with_known_issue_annotation": 0,
                "issue_relevant_in_top5_rate": None,
                "mean_relevant_statutes_in_top5": None}
    return {
        "cases_with_known_issue_annotation": len(known),
        "issue_relevant_in_top5_rate": sum(row["issue_relevant_in_top5"] for row in known) / len(known),
        "mean_relevant_statutes_in_top5": sum(row["number_relevant_in_top5"] for row in known) / len(known),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def index_unique(records: Iterable[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        case_id = str(record["case_id"])
        if case_id in result:
            raise ValueError(f"Duplicate case_id {case_id} in {label}")
        result[case_id] = record
    return result


def load_eval(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        report = json.load(handle)
    if report.get("protocol", {}).get("split") != "development":
        raise ValueError(f"Expected development evaluation: {path}")
    return report, index_unique(report["cases"], str(path))


def development_ids(split_path: Path) -> set[str]:
    with split_path.open(encoding="utf-8", newline="") as handle:
        return {row["case_id"] for row in csv.DictReader(handle) if row["split"] == "development"}


def validate_case_sets(expected: set[str], sources: dict[str, dict[str, Any]]) -> None:
    for label, records in sources.items():
        actual = set(records)
        if actual != expected:
            raise ValueError(f"{label} case IDs differ: missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    if set(CASE_ISSUES) != expected:
        raise ValueError("CASE_ISSUES must cover exactly the frozen development split")


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# B2 Retrieval Diagnostic", "", "## Summary", "",
        f"- Development cases: {summary['development_cases']}",
        f"- Known issue annotations: {summary['cases_with_known_issue_annotation']}/{summary['development_cases']}",
        f"- Top-5 issue relevance rate (known annotations only): {summary['issue_relevant_in_top5_rate']:.4f}",
        f"- Mean relevant statutes retrieved in top-5 (known annotations only): {summary['mean_relevant_statutes_in_top5']:.4f}",
        f"- Unknown relevance annotations: {', '.join(summary['unknown_annotation_case_ids']) or 'none'}", "",
        "## Paired B0 vs B2", "",
        "| Case | B0 exact | B2 exact | B0 F1 | B2 F1 | Relevant in top-5 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["cases"]:
        relevance = "unknown" if row["issue_relevant_in_top5"] is None else str(row["issue_relevant_in_top5"])
        lines.append(f"| {row['case_id']} | {int(row['b0_allocation_exact'])} | {int(row['b2_allocation_exact'])} | {row['b0_heir_f1']:.4f} | {row['b2_heir_f1']:.4f} | {relevance} |")

    headings = {
        "A": "B0 wrong → B2 correct",
        "B": "B0 wrong → B2 wrong + relevant",
        "C": "B0 wrong → B2 wrong + irrelevant",
        "D": "B0 correct → B2 wrong",
        "E": "B0 correct → B2 correct",
        "U": "B0 wrong → B2 wrong + unknown relevance",
    }
    lines += ["", "## Error transition groups", ""]
    by_group = {group: [row for row in report["cases"] if row["transition_group"] == group] for group in headings}
    for group, heading in headings.items():
        lines += [f"### Group {group}: {heading}", "", "| Case | Relevance | Retrieved statutes |", "| --- | ---: | --- |"]
        if not by_group[group]:
            lines.append("| — | — | — |")
        for row in by_group[group]:
            relevance = "unknown" if row["issue_relevant_in_top5"] is None else str(row["issue_relevant_in_top5"])
            lines.append(f"| {row['case_id']} | {relevance} | {', '.join(row['retrieved_statute_ids'])} |")
        lines.append("")

    lines += ["## Retrieval inspection", ""]
    for row in report["cases"]:
        relevant = "unknown" if row["relevant_statute_ids"] is None else ", ".join(row["relevant_statute_ids"])
        lines += [
            f"### Case {row['case_id']}", "",
            f"- Dominant issue(s): {', '.join(row['dominant_issues'])}",
            f"- Relevant statute IDs: {relevant}",
            f"- Retrieved top-5: {', '.join(row['retrieved_statute_ids'])}",
            f"- Relevant retrieved IDs: {', '.join(row['relevant_retrieved_ids']) or 'none'}",
            f"- Best relevant rank: {row['relevant_rank'] if row['relevant_rank'] is not None else 'none'}",
            f"- B0 exact: {row['b0_allocation_exact']}",
            f"- B2 exact: {row['b2_allocation_exact']}",
        ]
        if row.get("annotation_note"):
            lines.append(f"- Annotation note: {row['annotation_note']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    b0_report, b0_eval = load_eval(args.b0_eval)
    b2_report, b2_eval = load_eval(args.b2_eval)
    b0_predictions = index_unique(load_jsonl(args.b0_predictions), str(args.b0_predictions))
    b2_predictions = index_unique(load_jsonl(args.b2_predictions), str(args.b2_predictions))
    b0_trace = index_unique(load_jsonl(args.b0_trace), str(args.b0_trace))
    b2_trace = index_unique(load_jsonl(args.b2_trace), str(args.b2_trace))
    expected = development_ids(args.split_manifest)
    validate_case_sets(expected, {"B0 evaluation": b0_eval, "B2 evaluation": b2_eval,
                                  "B0 predictions": b0_predictions, "B2 predictions": b2_predictions,
                                  "B0 trace": b0_trace, "B2 trace": b2_trace})

    corpus_ids = {row["citation_id"] for row in load_jsonl(args.corpus)}
    annotated_ids = {sid for item in CASE_ISSUES.values() for sid in (item["relevant_statutes"] or [])}
    missing_statutes = sorted(annotated_ids - corpus_ids)
    if missing_statutes:
        raise ValueError(f"Annotated citation IDs absent from corpus: {missing_statutes}")

    cases = []
    for case_id in sorted(expected, key=int):
        annotation = CASE_ISSUES[case_id]
        retrieved = b2_trace[case_id].get("retrieved_statute_ids")
        if not isinstance(retrieved, list) or len(retrieved) != 5:
            raise ValueError(f"Case {case_id} does not have exactly five retrieved_statute_ids")
        diagnostic = retrieval_diagnostic(retrieved, annotation["relevant_statutes"])
        b0_exact = bool(b0_eval[case_id]["allocation_exact"])
        b2_exact = bool(b2_eval[case_id]["allocation_exact"])
        row = {
            "case_id": case_id,
            "b0_allocation_exact": b0_exact,
            "b2_allocation_exact": b2_exact,
            "b0_heir_f1": b0_eval[case_id]["heir_f1"],
            "b2_heir_f1": b2_eval[case_id]["heir_f1"],
            "b2_predicted_total_matches_reference": b2_eval[case_id]["predicted_total_matches_reference"],
            "dominant_issues": annotation["issues"],
            "relevant_statute_ids": annotation["relevant_statutes"],
            "retrieved_statute_ids": retrieved,
            **diagnostic,
        }
        if "annotation_note" in annotation:
            row["annotation_note"] = annotation["annotation_note"]
        row["transition_group"] = transition_group(b0_exact, b2_exact, diagnostic["issue_relevant_in_top5"])
        cases.append(row)

    relevance_summary = aggregate_relevance(cases)
    groups = {group: [row["case_id"] for row in cases if row["transition_group"] == group] for group in "ABCDEU"}
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "scope": "frozen B0/B2 development artifacts; no retrieval or model execution",
        "sources": {key: str(value) for key, value in {
            "b0_predictions": args.b0_predictions, "b0_trace": args.b0_trace, "b0_evaluation": args.b0_eval,
            "b2_predictions": args.b2_predictions, "b2_trace": args.b2_trace, "b2_evaluation": args.b2_eval,
            "split_manifest": args.split_manifest, "statute_corpus": args.corpus}.items()},
        "baseline_metrics": {"b0": b0_report["metrics"], "b2": b2_report["metrics"]},
        "summary": {
            "development_cases": len(cases),
            **relevance_summary,
            "issue_annotation_coverage": relevance_summary["cases_with_known_issue_annotation"] / len(cases),
            "unknown_annotation_case_ids": [row["case_id"] for row in cases if row["issue_relevant_in_top5"] is None],
            "transition_groups": groups,
            "transition_group_counts": {group: len(ids) for group, ids in groups.items()},
        },
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {
        "b0_predictions": ROOT / "data/runs/allocation_dev_b0.jsonl",
        "b0_trace": ROOT / "data/runs/allocation_dev_b0.trace.jsonl",
        "b0_eval": ROOT / "data/eval/allocation_dev_b0.json",
        "b2_predictions": ROOT / "data/runs/allocation_dev_b2.jsonl",
        "b2_trace": ROOT / "data/runs/allocation_dev_b2.trace.jsonl",
        "b2_eval": ROOT / "data/eval/allocation_dev_b2.json",
        "split_manifest": ROOT / "data/release/split.csv",
        "corpus": ROOT / "data/legal_corpus/normalized/statutes.jsonl",
        "output_json": ROOT / "data/eval/b2_retrieval_diagnostic.json",
        "output_md": ROOT / "data/eval/b2_retrieval_diagnostic.md",
    }
    for name, default in defaults.items():
        parser.add_argument("--" + name.replace("_", "-"), type=Path, default=default)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(markdown_report(report), encoding="utf-8")
    summary = report["summary"]
    print(f"Analyzed {summary['development_cases']} frozen development cases.")
    print(f"Known issue annotations: {summary['cases_with_known_issue_annotation']}")
    print(f"Top-5 issue relevance rate: {summary['issue_relevant_in_top5_rate']:.4f}")
    print(f"Mean relevant statutes in top-5: {summary['mean_relevant_statutes_in_top5']:.4f}")
    print(f"JSON report: {args.output_json}")
    print(f"Markdown report: {args.output_md}")


if __name__ == "__main__":
    main()
