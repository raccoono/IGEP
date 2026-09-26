#!/usr/bin/env python3
"""Build a versioned, article-level Vietnamese civil-law corpus from DOCX.

The source DOCX files are immutable inputs. Each output record retains the
article heading and every body paragraph, with clause/point line types added
without rewriting the source text.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "data/legal_corpus"
MANIFEST_PATH = CORPUS_ROOT / "manifest.csv"
OUTPUT_PATH = CORPUS_ROOT / "normalized/statutes.jsonl"

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
ARTICLE_RE = re.compile(r"^\s*Điều\s+(\d+)\s*[\.:]\s*(.*)\s*$", re.I)
CLAUSE_RE = re.compile(r"^\s*(\d+)\s*[\.\-]\s+(.+)$")
POINT_RE = re.compile(r"^\s*([a-zđ])\)\s*(.+)$", re.I)


@dataclass(frozen=True)
class Document:
    document_id: str
    title: str
    number: str
    document_type: str
    promulgation_date: str
    effective_from: str
    effective_to: str
    source_url: str
    source_path: str
    expected_articles: int
    inheritance_from: int
    inheritance_to: int


DOCUMENTS = (
    Document(
        "PLTK_1990",
        "Pháp lệnh Thừa kế 1990",
        "44-LCT/HĐNN8",
        "ordinance",
        "1990-08-30",
        "1990-09-10",
        "1996-06-30",
        "https://vbpl.vn/botuphap/Pages/vbpq-print.aspx?ItemID=2057",
        "sources/PLTK_1990/original.docx",
        38,
        1,
        38,
    ),
    Document(
        "BLDS_1995",
        "Bộ luật Dân sự 1995",
        "Không số (Lệnh công bố 44-L/CTN)",
        "civil_code",
        "1995-10-28",
        "1996-07-01",
        "2005-12-31",
        "https://vbpl.vn/Toaannhandantoicao/Pages/vbpq-toanvan.aspx?ItemID=9683",
        "sources/BLDS_1995/original.docx",
        838,
        634,
        689,
    ),
    Document(
        "BLDS_2005",
        "Bộ luật Dân sự 2005",
        "33/2005/QH11",
        "civil_code",
        "2005-06-14",
        "2006-01-01",
        "2016-12-31",
        "https://vbpl.vn/TW/Pages/ivbpq-toanvan.aspx?ItemID=18128",
        "sources/BLDS_2005/original.docx",
        777,
        631,
        687,
    ),
    Document(
        "BLDS_2015",
        "Bộ luật Dân sự 2015",
        "91/2015/QH13",
        "civil_code",
        "2015-11-24",
        "2017-01-01",
        "",
        "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=95942",
        "sources/BLDS_2015/original.docx",
        689,
        609,
        662,
    ),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docx_paragraphs(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", WORD_NS):
        text = "".join(
            node.text or "" for node in paragraph.findall(".//w:t", WORD_NS)
        ).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def provision_lines(paragraphs: list[str]) -> list[dict[str, str | None]]:
    result = []
    current_clause: str | None = None
    for text in paragraphs:
        clause_match = CLAUSE_RE.match(text)
        point_match = POINT_RE.match(text)
        if clause_match:
            current_clause = clause_match.group(1)
            result.append(
                {
                    "type": "clause",
                    "clause_id": current_clause,
                    "point_id": None,
                    "text": text,
                }
            )
        elif point_match:
            result.append(
                {
                    "type": "point",
                    "clause_id": current_clause,
                    "point_id": point_match.group(1).lower(),
                    "text": text,
                }
            )
        else:
            result.append(
                {
                    "type": "paragraph",
                    "clause_id": current_clause,
                    "point_id": None,
                    "text": text,
                }
            )
    return result


def article_records(document: Document) -> list[dict]:
    source = CORPUS_ROOT / document.source_path
    paragraphs = docx_paragraphs(source)
    heading_positions: list[tuple[int, int, str]] = []
    for index, text in enumerate(paragraphs):
        match = ARTICLE_RE.match(text)
        if match:
            heading_positions.append((index, int(match.group(1)), match.group(2).strip()))

    records = []
    for position, (start, article_id, title) in enumerate(heading_positions):
        stop = (
            heading_positions[position + 1][0]
            if position + 1 < len(heading_positions)
            else len(paragraphs)
        )
        heading = paragraphs[start]
        body = paragraphs[start + 1 : stop]

        # Structural labels between articles belong to the next hierarchy, not
        # to the preceding article. They occur as a trailing uppercase block.
        while body and (
            re.match(r"^(PHẦN|CHƯƠNG|MỤC)\b", body[-1])
            or (body[-1].isupper() and len(body[-1]) < 180)
        ):
            body.pop()

        # The DOCX exports append enactment attestations and signatures after
        # the final article. They are document metadata, not article content.
        for footer_index, paragraph in enumerate(body):
            if re.match(r"^Bộ luật này đã được Quốc hội\b", paragraph, re.I):
                body = body[:footer_index]
                break

        records.append(
            {
                "citation_id": f"VN_{document.document_id}_ART_{article_id}",
                "document_id": document.document_id,
                "document_title": document.title,
                "document_number": document.number,
                "article_id": str(article_id),
                "article_number": article_id,
                "article_title": title,
                "effective_from": document.effective_from,
                "effective_to": document.effective_to or None,
                "inheritance_relevant": (
                    document.inheritance_from <= article_id <= document.inheritance_to
                ),
                "heading": heading,
                "body_paragraphs": body,
                "provisions": provision_lines(body),
                "text": "\n".join([heading, *body]),
                "retrieval_text": "\n".join(
                    [document.title, document.number, heading, *body]
                ),
                "source_url": document.source_url,
                "source_file": document.source_path,
                "source_file_sha256": sha256(source),
            }
        )
    return records


def write_manifest(documents: tuple[Document, ...]) -> None:
    fields = [
        "document_id",
        "document_title",
        "document_number",
        "document_type",
        "promulgation_date",
        "effective_from",
        "effective_to",
        "official_source_url",
        "source_url_basis",
        "local_source_path",
        "source_file_sha256",
        "expected_article_count",
        "inheritance_article_range",
        "collection_status",
        "review_status",
    ]
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for document in documents:
            source = CORPUS_ROOT / document.source_path
            writer.writerow(
                {
                    "document_id": document.document_id,
                    "document_title": document.title,
                    "document_number": document.number,
                    "document_type": document.document_type,
                    "promulgation_date": document.promulgation_date,
                    "effective_from": document.effective_from,
                    "effective_to": document.effective_to,
                    "official_source_url": document.source_url,
                    "source_url_basis": "official_record_matched_by_document_number",
                    "local_source_path": document.source_path,
                    "source_file_sha256": sha256(source),
                    "expected_article_count": document.expected_articles,
                    "inheritance_article_range": (
                        f"{document.inheritance_from}-{document.inheritance_to}"
                    ),
                    "collection_status": "complete_full_text",
                    "review_status": "machine_validated_pending_legal_review",
                }
            )


def main() -> None:
    records = []
    for document in DOCUMENTS:
        records.extend(article_records(document))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    write_manifest(DOCUMENTS)
    print(f"Documents: {len(DOCUMENTS)}")
    print(f"Articles: {len(records)}")
    for document in DOCUMENTS:
        count = sum(r["document_id"] == document.document_id for r in records)
        relevant = sum(
            r["document_id"] == document.document_id and r["inheritance_relevant"]
            for r in records
        )
        print(f"{document.document_id}: {count} articles; {relevant} inheritance-relevant")
    print(MANIFEST_PATH)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
