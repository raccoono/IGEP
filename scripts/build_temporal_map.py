#!/usr/bin/env python3
"""Build a reviewable temporal-law map from the canonical IGEP artifacts.

This script deliberately produces candidate regimes, not adjudicated legal
gold. Dates and evidence must be present in the runtime query; missing or
boundary-imprecise dates are labelled AMBIGUOUS rather than inferred.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data/canonical/input.jsonl"
GOLD_PATH = ROOT / "data/canonical/gold.json"
CSV_PATH = ROOT / "data/review/temporal_map.csv"

DEATH_WORDS = r"chết|mất|qua đời|hy sinh|từ trần"
DATE_PATTERNS = [
    re.compile(r"(?:ngày\s+)?(\d{1,2})[/-](\d{1,2})[/-](\d{4})", re.I),
    re.compile(r"tháng\s+(\d{1,2})[/-](\d{4})", re.I),
    re.compile(r"(?:năm|năm\s+)(\d{4})", re.I),
    re.compile(r"(?:chết|mất|qua đời|hy sinh)\s+(?:vào\s+)?(?:năm\s+)?(\d{4})", re.I),
]

# Deterministic corrections for compact sentences containing multiple deaths.
# Every value below is directly supported by the quoted runtime query. Keeping
# these here makes the human-readable audit reproducible without silently
# teaching the generic heuristic case-specific linguistic assumptions.
DATE_OVERRIDES = {
    ("12", "Trần Thị Lâm"): ("Hai năm sau năm 1991", "1993", "year_relative"),
    ("57", "N1"): ("Năm 2021", "2021", "year"),
    ("59", "Nguyễn Thị T2"): ("năm 1999", "1999", "year"),
    ("77", "Hoàng Đình M"): ("Sau đó cùng năm [2011]", "2011", "year_relative"),
    ("92", "S"): ("Năm 1992", "1992", "year"),
    ("113", "C"): ("chết năm 2009", "2009", "year"),
    ("123", "C"): ("chết 1997", "1997", "year"),
    ("127", "C"): ("chết năm 2018", "2018", "year"),
    ("130", "C"): ("chết năm 2019", "2019", "year"),
    ("117", "Thuyết"): ("chết 2017", "2017", "year"),
    ("117", "Lược"): ("chết 2000", "2000", "year"),
    ("117", "Tiêu"): ("chết 2011", "2011", "year"),
    ("128", "H1"): ("chết năm 2022", "2022", "year"),
}

# The death date is not stated exactly, but the query places death after an
# event whose date is explicit and wholly within the BLDS 2015 period.
RELATIVE_CHRONOLOGY_OVERRIDES = {
    ("17", "Nguyễn Văn Phát"): (
        "Sau đầu năm 2021",
        "2021",
        "year_inferred_from_relative_chronology",
        "Death occurs after the will made in early 2021.",
    ),
    ("18", "Nguyễn Văn Kha"): (
        "Sau năm 2020",
        "2020",
        "year_inferred_from_relative_chronology",
        "Death occurs after the will made in 2020.",
    ),
    ("42", "Phạm Văn P"): (
        "Sau đầu năm 2024 một tháng",
        "2024",
        "year_inferred_from_relative_chronology",
        "Death occurs one month after the fire in early 2024.",
    ),
}

BEFORE_BOUNDARY_OVERRIDES = {
    ("69", "M"): ("trước ngày 10/09/1990", "<1990-09-10", "before_day", "PRE_1990"),
    ("90", "Nguyễn Đức M"): ("trước ngày 10/09/1990", "<1990-09-10", "before_day", "PRE_1990"),
    ("98", "Huỳnh Thị T5"): ("trước ngày 01/07/1996", "<1996-07-01", "before_day", "PLTK_1990"),
    ("149", "Lê Tín Đ"): ("trước ngày 01/07/1996", "<1996-07-01", "before_day", "PLTK_1990"),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def name_tokens(name: str) -> list[str]:
    return [token for token in name.split() if len(token) > 1]


def score_sentence(sentence: str, target: str) -> int:
    if not re.search(rf"\b(?:{DEATH_WORDS})\b", sentence, re.I):
        return -1
    score = 0
    if target in sentence:
        score += 20
    tokens = name_tokens(target)
    score += sum(2 for token in tokens if token in sentence)
    if re.search(r"\d{4}", sentence):
        score += 4
    if re.search(rf"{re.escape(target)}[^.!?]{{0,30}}(?:{DEATH_WORDS})", sentence, re.I):
        score += 10
    return score


def select_evidence(query: str, target: str) -> str:
    ranked = sorted(
        ((score_sentence(sentence, target), sentence) for sentence in sentences(query)),
        reverse=True,
    )
    if ranked and ranked[0][0] >= 2:
        return ranked[0][1]
    return ""


def extract_date(evidence: str, target: str) -> tuple[str, str, str]:
    """Return source text, normalized date and precision.

    Prefer a date immediately attached to the target/death expression. The
    evidence is still exposed for reviewer correction where a sentence has
    multiple persons or dates.
    """
    if not evidence:
        return "", "", "unknown"

    target_pos = evidence.find(target)
    death_matches = list(re.finditer(rf"\b(?:{DEATH_WORDS})\b", evidence, re.I))
    anchor = target_pos if target_pos >= 0 else (death_matches[0].start() if death_matches else 0)
    candidates: list[tuple[int, str, str, str]] = []
    for index, pattern in enumerate(DATE_PATTERNS):
        for match in pattern.finditer(evidence):
            distance = abs(match.start() - anchor)
            if index == 0:
                day, month, year = map(int, match.groups())
                candidates.append((distance, match.group(0), f"{year:04d}-{month:02d}-{day:02d}", "day"))
            elif index == 1:
                month, year = map(int, match.groups())
                candidates.append((distance, match.group(0), f"{year:04d}-{month:02d}", "month"))
            else:
                year = int(match.group(1))
                candidates.append((distance, match.group(0), f"{year:04d}", "year"))
    if not candidates:
        return "", "", "unknown"
    _, source, normalized, precision = min(candidates, key=lambda item: item[0])
    return source, normalized, precision


def regime(date: str, precision: str) -> tuple[str, str]:
    if not date:
        return "AMBIGUOUS", "missing_opening_date"
    year = int(date[:4])
    if precision == "year" and year in {1990, 1996}:
        return "AMBIGUOUS", "effective_date_boundary_with_year_only"
    sortable = date + ("-01-01"[len(date) - 4 :] if len(date) < 10 else "")
    if sortable < "1990-09-10":
        return "PRE_1990", "candidate_requires_historical_source_review"
    if sortable < "1996-07-01":
        return "PLTK_1990", "candidate_requires_legal_review"
    if sortable < "2006-01-01":
        return "BLDS_1995", "candidate_requires_legal_review"
    if sortable < "2017-01-01":
        return "BLDS_2005", "candidate_requires_legal_review"
    return "BLDS_2015", "candidate_requires_legal_review"


def yes_no_unknown(query: str, patterns: list[str]) -> str:
    return "yes" if any(re.search(pattern, query, re.I) for pattern in patterns) else "no"


def build_rows() -> list[dict[str, str]]:
    inputs = {row["case_id"]: row for row in read_jsonl(INPUT_PATH)}
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for record in gold:
        case_id = record["case_id"]
        query = inputs[case_id]["query_text"]
        targets = record["target_decedents"]
        for opening_index, target in enumerate(targets, 1):
            evidence = select_evidence(query, target)
            date_text, normalized, precision = extract_date(evidence, target)
            if (case_id, target) in DATE_OVERRIDES:
                date_text, normalized, precision = DATE_OVERRIDES[(case_id, target)]
            mismatch_note = ""
            assignment_basis = "explicit_opening_date"
            temporal_selection_eligible = "yes"
            if (case_id, target) in BEFORE_BOUNDARY_OVERRIDES:
                date_text, normalized, precision, candidate = BEFORE_BOUNDARY_OVERRIDES[(case_id, target)]
                status = "regime_determinate_from_benchmark_upper_bound"
                assignment_basis = "benchmark_temporal_stipulation"
            elif (case_id, target) in RELATIVE_CHRONOLOGY_OVERRIDES:
                date_text, normalized, precision, mismatch_note = (
                    RELATIVE_CHRONOLOGY_OVERRIDES[(case_id, target)]
                )
                candidate = "BLDS_2015"
                status = "regime_determinate_from_relative_chronology"
                assignment_basis = "relative_chronology"
            else:
                candidate, status = regime(normalized, precision)
            if status == "missing_opening_date":
                candidate = "BLDS_2015"
                status = "undated_current_law_assumption"
                assignment_basis = "benchmark_stipulation"
                temporal_selection_eligible = "no"
                mismatch_note = (
                    "No opening date is stated; BLDS 2015 is stipulated for reasoning, "
                    "retrieval and allocation only."
                )
            rows.append(
                {
                    "case_id": case_id,
                    "opening_index": str(opening_index),
                    "decedent": target,
                    "opening_date_text": date_text,
                    "opening_date_normalized": normalized,
                    "date_precision": precision,
                    "candidate_regime": candidate,
                    "temporal_status": status,
                    "regime_assignment_basis": assignment_basis,
                    "temporal_selection_eligible": temporal_selection_eligible,
                    "evidence": evidence,
                    "has_historical_will": yes_no_unknown(query, [r"di chúc", r"chúc thư"]),
                    "has_historical_transaction": yes_no_unknown(
                        query,
                        [r"tặng cho", r"chuyển nhượng", r"mua bán", r"thỏa thuận", r"từ chối nhận di sản", r"khước từ"],
                    ),
                    "requires_transition_rule": "to_review" if candidate != "BLDS_2015" else "no",
                    "requires_external_law": yes_no_unknown(
                        query,
                        [r"quyền sử dụng đất", r"thửa đất", r"kết hôn", r"ly hôn", r"tài sản chung", r"hôn nhân"],
                    ),
                    "review_decision": "",
                    "review_note": mismatch_note,
                }
            )
    return rows


def write_csv(rows: list[dict[str, str]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict[str, str]]) -> None:
    by_regime = Counter(row["candidate_regime"] for row in rows)
    by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)
    ambiguous = [row for row in rows if row["candidate_regime"] == "AMBIGUOUS"]
    stipulated = [
        row for row in rows if row["temporal_status"] == "undated_current_law_assumption"
    ]
    relative = [
        row
        for row in rows
        if row["temporal_status"] == "regime_determinate_from_relative_chronology"
    ]
    lines = [
        "# Temporal legal-regime audit — candidate map",
        "",
        "## Status and scope",
        "",
        "This file maps every target succession opening in the 150-case canonical benchmark.",
        "It is a **candidate annotation for legal review**, not adjudicated temporal-law gold.",
        "Dates are copied from runtime query evidence; missing dates are never invented.",
        "The candidate regime concerns the succession opening only. Will execution, property,",
        "marriage, land, transactions and limitation periods may require a different event-time",
        "analysis and transitional rules.",
        "",
        "The former `blds2015_standardization_audit.md` is superseded by the temporal-law",
        "direction and must not be used as the active benchmark protocol.",
        "",
        "## Candidate regime boundaries",
        "",
        "- `PRE_1990`: before 10 September 1990; source-by-source historical review required.",
        "- `PLTK_1990`: 10 September 1990–30 June 1996.",
        "- `BLDS_1995`: 1 July 1996–31 December 2005.",
        "- `BLDS_2005`: 1 January 2006–31 December 2016.",
        "- `BLDS_2015`: from 1 January 2017.",
        "- `AMBIGUOUS`: only a boundary year (1990/1996) is stated.",
        "- `undated_current_law_assumption`: no opening date is stated; BLDS 2015 is",
        "  stipulated for non-temporal modules and the opening is excluded from temporal selection.",
        "",
        "## Coverage summary",
        "",
        f"- Canonical cases covered: {len(by_case)} / 150",
        f"- Target succession openings mapped: {len(rows)}",
        f"- Openings assigned by relative chronology: {len(relative)}",
        f"- Undated openings stipulated under BLDS 2015: {len(stipulated)}",
        f"- Openings eligible for temporal-law-selection scoring: {sum(row['temporal_selection_eligible'] == 'yes' for row in rows)}",
    ]
    for label in ["PRE_1990", "PLTK_1990", "BLDS_1995", "BLDS_2005", "BLDS_2015", "AMBIGUOUS"]:
        lines.append(f"- `{label}`: {by_regime[label]}")
    lines.extend(
        [
            "",
            "Cases 69, 90, 98 and 149 use author-approved benchmark upper-bound",
            "stipulations to resolve the former 1990/1996 effective-date ambiguity.",
            "These are benchmark adaptations, not claims that the precise upper bounds",
            "were present in the original source judgments.",
        ]
    )
    lines.extend(
        [
            "",
            "## Ambiguous openings requiring author/legal review",
            "",
            "| Case | Opening | Decedent | Date/evidence issue | Evidence |",
            "|---:|---:|---|---|---|",
        ]
    )
    for row in ambiguous:
        evidence = row["evidence"].replace("|", "\\|") or "—"
        issue = row["review_note"].replace("|", "\\|") or row["temporal_status"]
        lines.append(
            f"| {row['case_id']} | {row['opening_index']} | {row['decedent']} | "
            f"{issue} | {evidence} |"
        )
    lines.extend(
        [
            "",
            "## Undated current-law assumptions",
            "",
            "These openings use BLDS 2015 only because the benchmark stipulates that policy.",
            "They remain usable for retrieval, reasoning and allocation, but are excluded from",
            "the temporal-law-selection metric.",
            "",
            "| Case | Opening | Decedent | Candidate regime | Selection eligible |",
            "|---:|---:|---|---|---|",
        ]
    )
    for row in stipulated:
        lines.append(
            f"| {row['case_id']} | {row['opening_index']} | {row['decedent']} | "
            f"{row['candidate_regime']} | {row['temporal_selection_eligible']} |"
        )
    lines.extend(
        [
            "",
            "## Complete case map",
            "",
            "| Case | Opening | Decedent | Opening date | Precision | Candidate regime | Status |",
            "|---:|---:|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['opening_index']} | {row['decedent']} | "
            f"{row['opening_date_normalized'] or '—'} | {row['date_precision']} | "
            f"{row['candidate_regime']} | {row['temporal_status']} |"
        )
    lines.extend(
        [
            "",
            "## Review instructions",
            "",
            "1. Review every `AMBIGUOUS` row against the source; do not infer a date from the judgment year.",
            "2. Confirm that every target decedent in a multi-estate case is genuinely within evaluation scope.",
            "3. Review `requires_transition_rule=to_review` at event level, not only by death year.",
            "4. Replace bare article numbers only after the regime and transitional analysis are approved.",
            "5. Fill `review_decision` and `review_note` in the CSV; retain the pre-review version for provenance.",
            "",
        ]
    )
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    rows = build_rows()
    write_csv(rows)
    print(f"Cases: {len({row['case_id'] for row in rows})}")
    print(f"Openings: {len(rows)}")
    print(f"Regimes: {dict(Counter(row['candidate_regime'] for row in rows))}")
    print(CSV_PATH)


if __name__ == "__main__":
    main()
