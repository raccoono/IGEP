"""Rewrite the CSV and create deterministic, format-clean artifacts.

This script performs only mechanical transformations. It does not correct legal
labels, infer missing entities, or promote the existing pseudo-annotations to
gold annotations. The source CSV is rewritten in place with its six defined
columns; unnamed trailing columns are discarded as accidental input.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_CSV = PROJECT_ROOT / "data" / "benchmark.csv"
RAW_EXTRACTION = PROJECT_ROOT / "data" / "extraction.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "canonical"

CORE_HEADERS = [
    "Case_ID",
    "Tags",
    "Source",
    "User_Query",
    "Expected_Articles",
    "Expected_Distribution",
]

SOURCE_NORMALIZATION = {
    "congbobanan.toaan.gov.vn": "https://congbobanan.toaan.gov.vn",
    "http://congbobanan.toaan.gov.vn": "https://congbobanan.toaan.gov.vn",
    "https://congbobanan.toaan.gov.vn": "https://congbobanan.toaan.gov.vn",
}

COURT_JUDGMENT_SOURCE = "https://congbobanan.toaan.gov.vn"
LEGAL_EDUCATION_SOURCES = {
    "Trường đại học Luật - Đại học Huế",
    "Trường đại học Kinh tế Luật - Đại học Quốc gia Thành phố Hồ Chí Minh",
}

# A stipulated legal premise is retained only when the runtime text does not
# contain enough underlying facts to reconstruct it.  Such cases remain usable
# for final allocation but are excluded from the metric for that premise.
STIPULATED_WILL_VALIDITY_CASES = {
    "1", "2", "3", "4", "18", "24", "28", "29", "33", "34", "41",
    "54", "56", "61", "127", "128", "138", "146",
}
ADJUDICATED_INTERMEDIATE_CASES = {
    "58": ["estate_scope_adjudication"],
    "92": ["contribution_quantification"],
}
STIPULATED_SCOPE_CASES = {
    "125": ["will_scope_validity"],
}

ARTICLE_SPLIT_RE = re.compile(r"[;,]")
ARTICLE_RE = re.compile(r"\d+")
AMOUNT_RE = re.compile(r"\d[\d.,\s]*")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_articles(raw: str, case_id: str) -> list[str]:
    articles = [
        token.strip() for token in ARTICLE_SPLIT_RE.split(raw) if token.strip()
    ]
    if not articles:
        raise ValueError(f"Case {case_id}: empty Expected_Articles")
    invalid = [article for article in articles if not ARTICLE_RE.fullmatch(article)]
    if invalid:
        raise ValueError(
            f"Case {case_id}: invalid article labels: {invalid!r}"
        )
    if len(articles) != len(set(articles)):
        raise ValueError(f"Case {case_id}: duplicate article labels")
    return articles


def classify_source(source: str, case_id: str) -> tuple[str, str]:
    """Return the documented case origin and reference-label interpretation."""

    if source == COURT_JUDGMENT_SOURCE:
        return "court_judgment_derived", "court_adjudicated_outcome"
    if source in LEGAL_EDUCATION_SOURCES:
        return "legal_education_case", "reviewed_educational_answer"
    raise ValueError(f"Case {case_id}: unclassified source: {source!r}")


def parse_amount(raw: str, case_id: str, recipient: str) -> int:
    normalized = raw.strip()
    if normalized.lower().endswith("đồng"):
        normalized = normalized[:-4].strip()
    if not AMOUNT_RE.fullmatch(normalized):
        raise ValueError(
            f"Case {case_id}: invalid amount for {recipient!r}: {raw!r}"
        )
    digits = re.sub(r"\D", "", normalized)
    if not digits:
        raise ValueError(
            f"Case {case_id}: amount contains no digits for {recipient!r}"
        )
    return int(digits)


def parse_distribution(raw: str, case_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for segment in raw.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        if ":" not in segment:
            raise ValueError(
                f"Case {case_id}: distribution entry has no colon: {segment!r}"
            )
        recipient, raw_amount = segment.rsplit(":", 1)
        recipient = recipient.strip()
        if not recipient:
            raise ValueError(f"Case {case_id}: empty recipient")
        entries.append(
            {
                "recipient": recipient,
                "amount": parse_amount(raw_amount, case_id, recipient),
                "currency": "VND",
                "recipient_type": None,
                "legal_role": None,
            }
        )

    if not entries:
        raise ValueError(f"Case {case_id}: empty Expected_Distribution")

    recipients = [entry["recipient"] for entry in entries]
    if len(recipients) != len(set(recipients)):
        raise ValueError(f"Case {case_id}: duplicate distribution recipients")
    return entries


def canonical_distribution(entries: list[dict[str, Any]]) -> str:
    return "; ".join(
        f"{entry['recipient']}: {entry['amount']}" for entry in entries
    )


def read_raw_csv() -> tuple[list[str], list[list[str]]]:
    with RAW_CSV.open(encoding="utf-8-sig", newline="") as handle:
        table = list(csv.reader(handle))
    if not table:
        raise ValueError("benchmark.csv is empty")
    header, rows = table[0], table[1:]
    if header[: len(CORE_HEADERS)] != CORE_HEADERS:
        raise ValueError(
            f"Unexpected core CSV headers: {header[:len(CORE_HEADERS)]!r}"
        )
    if any(cell.strip() for cell in header[len(CORE_HEADERS) :]):
        raise ValueError("Unexpected named columns after the six core columns")
    if len({len(row) for row in rows}) != 1 or any(
        len(row) != len(header) for row in rows
    ):
        raise ValueError("CSV rows do not have a consistent column count")
    return header, rows


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    content = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in records
    )
    path.write_text(content, encoding="utf-8")


def write_clean_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CORE_HEADERS,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def validate_generated_files(expected_case_ids: list[str]) -> None:
    input_records = [
        json.loads(line)
        for line in (OUTPUT_DIR / "input.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    reference_records = [
        json.loads(line)
        for line in (OUTPUT_DIR / "reference.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    if [record["case_id"] for record in input_records] != expected_case_ids:
        raise AssertionError("Generated input JSONL case IDs changed")
    if [record["case_id"] for record in reference_records] != expected_case_ids:
        raise AssertionError("Generated reference JSONL case IDs changed")

    forbidden_input_keys = {
        "expected_articles",
        "expected_distribution",
        "reference_articles",
        "reference_settlement",
        "ground_truth_for_scoring",
        "relationship_reasoning",
    }
    for record in input_records:
        leaked = forbidden_input_keys.intersection(record)
        if leaked:
            raise AssertionError(
                f"Gold fields leaked into input for case {record['case_id']}: "
                f"{sorted(leaked)}"
            )


def main() -> None:
    header, raw_rows = read_raw_csv()
    extraction_records = json.loads(RAW_EXTRACTION.read_text(encoding="utf-8-sig"))
    if not isinstance(extraction_records, list):
        raise ValueError("extraction.json must contain a list")

    clean_csv_rows: list[dict[str, str]] = []
    input_records: list[dict[str, Any]] = []
    reference_records: list[dict[str, Any]] = []
    format_changes: list[dict[str, Any]] = []

    case_ids: list[str] = []
    source_counts_raw: Counter[str] = Counter()
    source_counts_canonical: Counter[str] = Counter()

    for raw_row in raw_rows:
        core = dict(zip(CORE_HEADERS, raw_row[: len(CORE_HEADERS)]))
        case_id = core["Case_ID"].strip()
        if not case_id or not case_id.isdigit():
            raise ValueError(f"Invalid Case_ID: {core['Case_ID']!r}")
        if case_id in case_ids:
            raise ValueError(f"Duplicate Case_ID: {case_id}")
        case_ids.append(case_id)

        source_raw = core["Source"].strip()
        source = SOURCE_NORMALIZATION.get(source_raw, source_raw)
        source_type, reference_origin = classify_source(source, case_id)
        source_counts_raw[source_raw] += 1
        source_counts_canonical[source] += 1

        query_raw = core["User_Query"]
        query_text = query_raw.strip()
        tags = core["Tags"].strip()
        articles = parse_articles(core["Expected_Articles"], case_id)
        settlement = parse_distribution(core["Expected_Distribution"], case_id)

        canonical_articles = "; ".join(articles)
        canonical_settlement = canonical_distribution(settlement)

        changes: list[str] = []
        if query_text != query_raw:
            changes.append("trimmed_query_boundary_whitespace")
        if source != source_raw:
            changes.append("normalized_source")
        if canonical_articles != core["Expected_Articles"]:
            changes.append("normalized_article_delimiters_and_spacing")
        if canonical_settlement != core["Expected_Distribution"]:
            changes.append("normalized_distribution_amount_format_and_spacing")
        if changes:
            format_changes.append({"case_id": case_id, "changes": changes})

        clean_csv_rows.append(
            {
                "Case_ID": case_id,
                "Tags": tags,
                "Source": source,
                "User_Query": query_text,
                "Expected_Articles": canonical_articles,
                "Expected_Distribution": canonical_settlement,
            }
        )
        input_record: dict[str, Any] = {
            "case_id": case_id,
            "source": source,
            "source_type": source_type,
            "query_text": query_text,
        }
        if case_id in STIPULATED_WILL_VALIDITY_CASES:
            input_record["legal_premise_policy"] = (
                "contains_stipulated_legal_premise"
            )
            input_record["excluded_module_metrics"] = ["will_validity"]
        elif case_id in ADJUDICATED_INTERMEDIATE_CASES:
            input_record["legal_premise_policy"] = (
                "contains_adjudicated_intermediate"
            )
            input_record["excluded_module_metrics"] = (
                ADJUDICATED_INTERMEDIATE_CASES[case_id]
            )
        elif case_id in STIPULATED_SCOPE_CASES:
            input_record["legal_premise_policy"] = (
                "contains_stipulated_legal_premise"
            )
            input_record["excluded_module_metrics"] = (
                STIPULATED_SCOPE_CASES[case_id]
            )
        input_records.append(input_record)
        reference_records.append(
            {
                "case_id": case_id,
                "reference_articles": articles,
                "reference_settlement": settlement,
                "total_reference_amount": sum(
                    entry["amount"] for entry in settlement
                ),
                "reference_origin": reference_origin,
                # Dataset-level review confirmed by the author: all 150 cases
                # were checked independently by four reviewers. See
                # data/review/PROTOCOL.md for the exact scope and
                # the claims that cannot be reconstructed from stored artifacts.
                "audit_status": "independently_reviewed",
            }
        )

    extraction_by_id = {
        str(record.get("case_id")): record for record in extraction_records
    }
    if set(extraction_by_id) != set(case_ids):
        raise ValueError("CSV and extraction JSON do not contain the same case IDs")

    query_matches_after_trim = 0
    source_matches = 0
    for input_record in input_records:
        extraction = extraction_by_id[input_record["case_id"]]
        if str(extraction.get("query_text", "")).strip() == input_record["query_text"]:
            query_matches_after_trim += 1
        extraction_source = str(extraction.get("source", "")).strip()
        extraction_source = SOURCE_NORMALIZATION.get(
            extraction_source, extraction_source
        )
        if extraction_source == input_record["source"]:
            source_matches += 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_clean_csv(RAW_CSV, clean_csv_rows)
    write_jsonl(OUTPUT_DIR / "input.jsonl", input_records)
    write_jsonl(OUTPUT_DIR / "reference.jsonl", reference_records)

    audit = {
        "format_version": "1.0.0",
        "transformation_scope": "mechanical_format_cleanup_only",
        "source_files": {
            "benchmark.csv": {
                "sha256": sha256_file(RAW_CSV),
                "row_count": len(raw_rows),
                "column_count": len(CORE_HEADERS),
                "core_column_count": len(CORE_HEADERS),
                "unnamed_header_count": 0,
            },
            "extraction.json": {
                "sha256": sha256_file(RAW_EXTRACTION),
                "record_count": len(extraction_records),
            },
        },
        "generated_files": [
            "input.jsonl",
            "reference.jsonl",
        ],
        "counts": {
            "case_count": len(case_ids),
            "article_assignment_count": sum(
                len(record["reference_articles"]) for record in reference_records
            ),
            "distinct_article_count": len(
                {
                    article
                    for record in reference_records
                    for article in record["reference_articles"]
                }
            ),
            "settlement_entry_count": sum(
                len(record["reference_settlement"])
                for record in reference_records
            ),
            "court_judgment_derived_cases": sum(
                record["source_type"] == "court_judgment_derived"
                for record in input_records
            ),
            "legal_education_cases": sum(
                record["source_type"] == "legal_education_case"
                for record in input_records
            ),
            "cases_with_format_changes": len(format_changes),
            "query_matches_extraction_after_trim": query_matches_after_trim,
            "source_matches_extraction_raw": source_matches,
        },
        "source_counts_raw": dict(sorted(source_counts_raw.items())),
        "source_counts_canonical": dict(sorted(source_counts_canonical.items())),
        "format_changes_by_case": format_changes,
        "known_non_format_issues_not_modified": [
            "Reference articles have not been legally audited.",
            "Reference settlements have not been legally audited.",
            "Recipient type and legal role remain null.",
            "Pseudo-annotations have not been migrated to schema v2.2.",
            "Entity, relationship, temporal, and evidence errors remain untouched.",
        ],
    }
    validate_generated_files(case_ids)

    print(f"Created canonical artifacts in: {OUTPUT_DIR}")
    print(f"Cases: {len(case_ids)}")
    print(
        "Articles: "
        f"{audit['counts']['article_assignment_count']} assignments / "
        f"{audit['counts']['distinct_article_count']} distinct"
    )
    print(
        f"Settlement entries: {audit['counts']['settlement_entry_count']}"
    )
    print("Validation: PASS")


if __name__ == "__main__":
    main()
