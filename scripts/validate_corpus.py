#!/usr/bin/env python3
"""Validate manifest integrity and normalized article-level legal corpus."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "data/legal_corpus"
MANIFEST_PATH = CORPUS_ROOT / "manifest.csv"
CORPUS_PATH = CORPUS_ROOT / "normalized/statutes.jsonl"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> None:
    errors: list[str] = []
    manifest = list(csv.DictReader(MANIFEST_PATH.open(encoding="utf-8")))
    records = [
        json.loads(line)
        for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest_by_id = {row["document_id"]: row for row in manifest}
    if len(manifest_by_id) != len(manifest):
        fail(errors, "duplicate document_id in manifest")

    citation_ids: set[str] = set()
    article_keys: set[tuple[str, int]] = set()
    by_document: dict[str, list[dict]] = {key: [] for key in manifest_by_id}
    for index, record in enumerate(records, 1):
        prefix = f"record {index}"
        document_id = record.get("document_id")
        if document_id not in manifest_by_id:
            fail(errors, f"{prefix}: unknown document_id {document_id!r}")
            continue
        by_document[document_id].append(record)
        citation_id = record.get("citation_id")
        if citation_id in citation_ids:
            fail(errors, f"{prefix}: duplicate citation_id {citation_id}")
        citation_ids.add(citation_id)
        article_number = record.get("article_number")
        key = (document_id, article_number)
        if key in article_keys:
            fail(errors, f"{prefix}: duplicate article key {key}")
        article_keys.add(key)
        expected_citation = f"VN_{document_id}_ART_{article_number}"
        if citation_id != expected_citation:
            fail(errors, f"{prefix}: invalid citation_id {citation_id!r}")
        if not isinstance(record.get("text"), str) or not record["text"].strip():
            fail(errors, f"{prefix}: empty text")
        if not isinstance(record.get("body_paragraphs"), list):
            fail(errors, f"{prefix}: body_paragraphs is not a list")
        elif not record["body_paragraphs"]:
            fail(errors, f"{prefix}: empty article body")
        reconstructed = "\n".join([record.get("heading", ""), *record.get("body_paragraphs", [])])
        if record.get("text") != reconstructed:
            fail(errors, f"{prefix}: text does not preserve paragraph structure")
        if not isinstance(record.get("inheritance_relevant"), bool):
            fail(errors, f"{prefix}: inheritance_relevant is not boolean")
        if any(
            paragraph.lower().startswith("bộ luật này đã được quốc hội")
            for paragraph in record.get("body_paragraphs", [])
        ):
            fail(errors, f"{prefix}: enactment footer included in article body")

    for document_id, row in manifest_by_id.items():
        source = CORPUS_ROOT / row["local_source_path"]
        if not source.exists():
            fail(errors, f"{document_id}: source file missing")
        elif sha256(source) != row["source_file_sha256"]:
            fail(errors, f"{document_id}: source checksum mismatch")
        try:
            effective_from = date.fromisoformat(row["effective_from"])
            effective_to = date.fromisoformat(row["effective_to"]) if row["effective_to"] else None
            if effective_to and effective_to < effective_from:
                fail(errors, f"{document_id}: invalid effective date interval")
        except ValueError:
            fail(errors, f"{document_id}: malformed effective date")
        expected_count = int(row["expected_article_count"])
        numbers = sorted(record["article_number"] for record in by_document[document_id])
        expected_numbers = list(range(1, expected_count + 1))
        if numbers != expected_numbers:
            missing = sorted(set(expected_numbers) - set(numbers))
            extra = sorted(set(numbers) - set(expected_numbers))
            fail(errors, f"{document_id}: discontinuous articles; missing={missing}; extra={extra}")
        start, stop = map(int, row["inheritance_article_range"].split("-"))
        for record in by_document[document_id]:
            expected_tag = start <= record["article_number"] <= stop
            if record["inheritance_relevant"] != expected_tag:
                fail(errors, f"{record['citation_id']}: incorrect inheritance tag")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "document_count": len(manifest),
        "article_count": len(records),
        "inheritance_relevant_count": sum(r.get("inheritance_relevant") is True for r in records),
        "counts_by_document": {
            document_id: len(document_records)
            for document_id, document_records in by_document.items()
        },
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
