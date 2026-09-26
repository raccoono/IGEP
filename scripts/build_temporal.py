#!/usr/bin/env python3
"""Build draft, opening-level temporal citation references for IGEP.

The canonical reference is currently case-level and expressed as bare BLDS
2015 article numbers. This builder resolves those articles to legal concepts,
then proposes citations for the regime assigned to each succession opening.
Proposals involving historical law remain candidates until legal review.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "data/canonical/reference.jsonl"
TEMPORAL_MAP_PATH = ROOT / "data/review/temporal_map.csv"
CROSSWALK_PATH = ROOT / "data/legal_corpus/crosswalk/crosswalk.csv"
STATUTES_PATH = ROOT / "data/legal_corpus/normalized/statutes.jsonl"
OUTPUT_PATH = ROOT / "data/canonical/temporal.jsonl"
AUDIT_PATH = ROOT / "data/review/citation_audit.csv"
REVIEW_OVERRIDES_PATH = ROOT / "data/review/citation_reviews.json"

REGIME_TO_DOCUMENT = {
    "PLTK_1990": "PLTK_1990",
    "BLDS_1995": "BLDS_1995",
    "BLDS_2005": "BLDS_2005",
    "BLDS_2015": "BLDS_2015",
}


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def versioned_2015(article: str) -> str:
    return f"VN_BLDS_2015_ART_{int(article)}"


def split_citations(value: str) -> list[str]:
    return [citation for citation in value.split(";") if citation]


def build_crosswalk_index(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Index concepts by their BLDS 2015 citation.

    A citation may occur in more than one concept (for example, the lawful-will
    article also contains the special rules for oral wills). Preserving every
    candidate is safer than silently choosing one concept.
    """
    index: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        for citation in split_citations(row["BLDS_2015_citation_ids"]):
            index[citation].append(row)
    return index


def map_article(
    source_article: str,
    regime: str,
    crosswalk_index: dict[str, list[dict[str, str]]],
) -> dict:
    source_citation = versioned_2015(source_article)
    details = []
    target_document = REGIME_TO_DOCUMENT.get(regime)
    for concept in crosswalk_index.get(source_citation, []):
        # Same-regime versioning is an identity operation. Do not let a broad
        # many-article concept expand a BLDS 2015 source citation into sibling
        # articles. Historical mappings retain the full candidate bundle for
        # explicit review.
        if regime == "BLDS_2015":
            target = [source_citation]
        else:
            target = (
                split_citations(concept[f"{target_document}_citation_ids"])
                if target_document
                else []
            )
        details.append(
            {
                "concept_id": concept["concept_id"],
                "concept_label_vi": concept["concept_label_vi"],
                "crosswalk_relation": concept["relation"],
                "target_citations": target,
            }
        )
    return {
        "source_article": str(source_article),
        "source_citation": source_citation,
        "concept_candidates": details,
    }


def opening_status(
    regime: str,
    mappings: list[dict],
    opening_count: int,
) -> tuple[str, list[str]]:
    flags: list[str] = []
    if opening_count > 1:
        flags.append("case_level_reference_scope_requires_opening_review")
    if regime == "PRE_1990":
        flags.append("missing_pre_1990_legal_corpus")
        return "unmapped_missing_legal_corpus", flags
    if regime not in REGIME_TO_DOCUMENT:
        flags.append("unresolved_or_unsupported_regime")
        return "unmapped_regime", flags

    if regime == "BLDS_2015":
        status = "direct_same_regime"
    else:
        status = "candidate_requires_legal_review"

    for mapping in mappings:
        concepts = mapping["concept_candidates"]
        if not concepts:
            flags.append(f"source_citation_not_in_crosswalk:{mapping['source_citation']}")
            continue
        if any(not concept["target_citations"] for concept in concepts):
            flags.append(f"concept_without_target_citation:{mapping['source_citation']}")
        if regime != "BLDS_2015" and (
            len(concepts) > 1
            or any(len(concept["target_citations"]) > 1 for concept in concepts)
        ):
            flags.append(f"one_to_many_mapping_requires_review:{mapping['source_citation']}")
        if regime != "BLDS_2015" and any(
            concept["crosswalk_relation"] != "equivalent" for concept in concepts
        ):
            flags.append(f"substantive_change_requires_review:{mapping['source_citation']}")
    return status, sorted(set(flags))


def build_records() -> tuple[list[dict], list[dict[str, str]]]:
    references = {row["case_id"]: row for row in read_jsonl(REFERENCE_PATH)}
    temporal_rows = read_csv(TEMPORAL_MAP_PATH)
    crosswalk_rows = read_csv(CROSSWALK_PATH)
    crosswalk_index = build_crosswalk_index(crosswalk_rows)
    review_overrides = (
        json.loads(REVIEW_OVERRIDES_PATH.read_text(encoding="utf-8"))
        if REVIEW_OVERRIDES_PATH.exists()
        else {}
    )
    opening_counts = Counter(row["case_id"] for row in temporal_rows)

    records: list[dict] = []
    audit_rows: list[dict[str, str]] = []
    for temporal in temporal_rows:
        case_id = temporal["case_id"]
        if case_id not in references:
            raise ValueError(f"Temporal opening has no canonical reference: case {case_id}")
        reference = references[case_id]
        regime = temporal["candidate_regime"]
        mappings = [
            map_article(article, regime, crosswalk_index)
            for article in reference["reference_articles"]
        ]
        candidate_citations = sorted(
            {
                citation
                for mapping in mappings
                for concept in mapping["concept_candidates"]
                for citation in concept["target_citations"]
            }
        )
        status, flags = opening_status(regime, mappings, opening_counts[case_id])
        opening_id = f"case_{case_id}_opening_{temporal['opening_index']}"
        review = review_overrides.get(opening_id, {})
        reviewed_citations = review.get("reviewed_expected_citations", [])
        temporal_selection_eligible = review.get(
            "temporal_selection_eligible",
            temporal["temporal_selection_eligible"] == "yes",
        )
        record = {
            "schema_version": "1.0.0-draft",
            "case_id": case_id,
            "opening_id": opening_id,
            "opening_index": int(temporal["opening_index"]),
            "decedent": temporal["decedent"],
            "opening_date_text": temporal["opening_date_text"] or None,
            "opening_date_normalized": temporal["opening_date_normalized"] or None,
            "date_precision": temporal["date_precision"],
            "legal_regime": regime,
            "regime_assignment_basis": temporal["regime_assignment_basis"],
            "temporal_selection_eligible": temporal_selection_eligible,
            "source_reference_articles_blds2015": reference["reference_articles"],
            "candidate_expected_citations": candidate_citations,
            "mapping_details": mappings,
            "mapping_status": status,
            "review_flags": flags,
            "reviewed_expected_citations": reviewed_citations,
            "review_status": review.get("review_status", "pending_legal_review"),
            "review_decision": review.get("review_decision"),
            "review_note": review.get("review_note"),
            "provenance": {
                "reference_path": "data/canonical/reference.jsonl",
                "temporal_map_path": "data/review/temporal_map.csv",
                "crosswalk_path": "data/legal_corpus/crosswalk/crosswalk.csv",
            },
        }
        records.append(record)
        audit_rows.append(
            {
                "case_id": case_id,
                "opening_id": opening_id,
                "opening_index": temporal["opening_index"],
                "decedent": temporal["decedent"],
                "opening_date_normalized": temporal["opening_date_normalized"],
                "date_precision": temporal["date_precision"],
                "legal_regime": regime,
                "regime_assignment_basis": temporal["regime_assignment_basis"],
                "temporal_selection_eligible": (
                    "yes" if temporal_selection_eligible else "no"
                ),
                "source_article_count": str(len(reference["reference_articles"])),
                "candidate_citation_count": str(len(candidate_citations)),
                "candidate_expected_citations": ";".join(candidate_citations),
                "mapping_status": status,
                "review_flags": ";".join(flags),
                "reviewed_expected_citations": ";".join(reviewed_citations),
                "review_status": review.get("review_status", "pending_legal_review"),
                "review_decision": review.get("review_decision", ""),
                "review_note": review.get("review_note", ""),
            }
        )
    return records, audit_rows


def validate(records: list[dict], audit_rows: list[dict[str, str]]) -> None:
    statutes = {row["citation_id"]: row for row in read_jsonl(STATUTES_PATH)}
    temporal_count = len(read_csv(TEMPORAL_MAP_PATH))
    errors: list[str] = []
    if len(records) != temporal_count or len(audit_rows) != temporal_count:
        errors.append("Output count does not match temporal opening count")

    opening_ids = [record["opening_id"] for record in records]
    if len(opening_ids) != len(set(opening_ids)):
        errors.append("Duplicate opening_id")

    for record in records:
        regime = record["legal_regime"]
        expected_document = REGIME_TO_DOCUMENT.get(regime)
        citations = record["candidate_expected_citations"]
        if expected_document and not citations:
            errors.append(f"{record['opening_id']}: mapped regime has no candidate citations")
        if regime == "PRE_1990" and citations:
            errors.append(f"{record['opening_id']}: PRE_1990 must remain unmapped")
        for citation in citations:
            statute = statutes.get(citation)
            if statute is None:
                errors.append(f"{record['opening_id']}: unknown citation {citation}")
            elif statute["document_id"] != expected_document:
                errors.append(
                    f"{record['opening_id']}: {citation} does not match {regime}"
                )
        for citation in record["reviewed_expected_citations"]:
            statute = statutes.get(citation)
            if statute is None:
                errors.append(f"{record['opening_id']}: unknown reviewed citation {citation}")
            elif statute["document_id"] != expected_document:
                errors.append(
                    f"{record['opening_id']}: reviewed {citation} does not match {regime}"
                )
        for mapping in record["mapping_details"]:
            if mapping["source_citation"] not in statutes:
                errors.append(
                    f"{record['opening_id']}: unknown source {mapping['source_citation']}"
                )

    if errors:
        preview = "\n".join(f"- {error}" for error in errors[:30])
        raise ValueError(f"Temporal reference validation failed:\n{preview}")


def write_outputs(records: list[dict], audit_rows: list[dict[str, str]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)


def main() -> None:
    records, audit_rows = build_records()
    validate(records, audit_rows)
    write_outputs(records, audit_rows)
    statuses = Counter(record["mapping_status"] for record in records)
    review_statuses = Counter(record["review_status"] for record in records)
    eligibility = Counter(
        "eligible" if record["temporal_selection_eligible"] else "excluded"
        for record in records
    )
    print(f"Wrote {len(records)} opening records to {OUTPUT_PATH}")
    print(f"Wrote {len(audit_rows)} audit rows to {AUDIT_PATH}")
    print("Mapping status:", dict(sorted(statuses.items())))
    print("Review status:", dict(sorted(review_statuses.items())))
    print("Retrieval evaluation:", dict(sorted(eligibility.items())))


if __name__ == "__main__":
    main()
