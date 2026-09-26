#!/usr/bin/env python3
"""Render a single human-review packet for the 30-case development evaluation."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data/canonical/dev_gold_reviewed.json"
EVIDENCE = ROOT / "data/review/dev_gold_evidence.jsonl"
RAW = ROOT / "data/eval/extraction_dev_reviewed30.json"
NORMALIZED = ROOT / "data/eval/extraction_dev_reviewed30_normalized.json"
OUTPUT = ROOT / "data/review/dev_gold_full_review.md"


def main():
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    evidence = [json.loads(x) for x in EVIDENCE.read_text(encoding="utf-8").splitlines() if x]
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    norm = json.loads(NORMALIZED.read_text(encoding="utf-8"))
    raw_cases = {x["case_id"]: x for x in raw["cases"]}
    norm_cases = {x["case_id"]: x for x in norm["cases"]}
    evidence_counts = Counter(x["case_id"] for x in evidence)
    lines = [
        "# Development extraction: consolidated 30-case review",
        "",
        "Status: author-approved annotation policy; semantic records awaiting final field-by-field inspection.",
        "",
        "> Methodological warning: 25 records were initialized from the existing IGEP baseline and then corrected under the approved review decisions. Therefore these scores are diagnostic and must not be reported as an independent benchmark result until a reviewer verifies the gold without consulting predictions.",
        "",
        "## Aggregate diagnostic results",
        "",
        "| Evaluation | Cases | Schema valid | Graph valid | Content micro F1 | Exact match |",
        "|---|---:|---:|---:|---:|---:|",
        f'| Raw baseline | 30 | {raw["validation"]["schema_valid_rate"]:.4f} | {raw["validation"]["graph_valid_rate"]:.4f} | {raw["overall"]["content_micro"]["f1"]:.4f} | {raw["overall"]["case_exact_match_rate"]:.4f} |',
        f'| Normalized baseline | 30 | {norm["validation"]["schema_valid_rate"]:.4f} | {norm["validation"]["graph_valid_rate"]:.4f} | {norm["overall"]["content_micro"]["f1"]:.4f} | {norm["overall"]["case_exact_match_rate"]:.4f} |',
        "",
        "## Case index",
        "",
        "| Case | Targets | P/R/E/W/A/Ag/Ev/LA | Evidence | Raw F1 | Normalized F1 | Exact after normalization |",
        "|---:|---|---|---:|---:|---:|---|",
    ]
    for record in gold:
        cid = str(record["case_id"])
        counts = "/".join(str(len(record[k])) for k in ["persons", "relationships", "estates", "wills", "inheritance_actions", "agreements", "events", "legal_assertions"])
        lines.append(f'| {cid} | {", ".join(record["target_decedents"])} | {counts} | {evidence_counts[cid]} | {raw_cases[cid]["content_f1"]:.4f} | {norm_cases[cid]["content_f1"]:.4f} | {"yes" if norm_cases[cid]["case_exact_match"] else "no"} |')
    lines += [
        "",
        "Legend: `P/R/E/W/A/Ag/Ev/LA` = persons, relationships, estates, wills, inheritance actions, agreements, events, and legal assertions.",
        "",
        "## Final reviewer checklist",
        "",
        "- [ ] Inspect all canonical persons and aliases.",
        "- [ ] Confirm every relationship and qualifier against its evidence span.",
        "- [ ] Confirm that common property and estate interests are not double-counted.",
        "- [ ] Confirm wills, dispositions, actions, and agreements are explicit in the input.",
        "- [ ] Confirm party allegations are not encoded as narrative findings.",
        "- [ ] Confirm every evidence offset selects the quoted text in the frozen input.",
        "- [ ] Record corrections without editing the frozen input or baseline run.",
        "- [ ] After corrections, rebuild and rerun both evaluations.",
        "",
        "Detailed annotation decisions: `data/review/dev_gold_approval.md`  ",
        "Semantic gold: `data/canonical/dev_gold_reviewed.json`  ",
        "Evidence: `data/review/dev_gold_evidence.jsonl`  ",
        "Raw evaluation: `data/eval/extraction_dev_reviewed30.md`  ",
        "Normalized evaluation: `data/eval/extraction_dev_reviewed30_normalized.md`",
        "",
    ]
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
