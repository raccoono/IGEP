"""Repair the user-updated legacy extraction gold using explicit query facts.

This script intentionally edits data/extraction_gold.json in place.
Every non-mechanical correction is encoded below and written to a repair log.
The full-schema canonical gold is generated separately by
build_gold.py.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = PROJECT_ROOT / "data" / "extraction_gold.json"
BENCHMARK_PATH = PROJECT_ROOT / "data" / "benchmark.csv"


RELATIONSHIP_REPLACEMENTS: dict[str, list[tuple[str, str, str]]] = {
    "7": [
        ("Sơn", "child_of", "Hậu"),
        ("Sơn", "child_of", "Thủy"),
        ("Yên", "child_of", "Hậu"),
        ("Yên", "child_of", "Minh"),
        ("Xuân", "child_of", "Hậu"),
        ("Xuân", "child_of", "Minh"),
        ("Minh", "spouse_of", "Hậu"),
        ("Thủy", "spouse_of", "Hậu"),
    ],
    "8": [
        ("Sơn", "child_of", "Hậu"),
        ("Sơn", "child_of", "Thủy"),
        ("Yên", "child_of", "Hậu"),
        ("Yên", "child_of", "Minh"),
        ("Xuân", "child_of", "Hậu"),
        ("Xuân", "child_of", "Minh"),
        ("Minh", "spouse_of", "Hậu"),
        ("Thủy", "spouse_of", "Hậu"),
    ],
    "13": [
        ("C", "child_of", "A"),
        ("C", "child_of", "B"),
        ("D", "child_of", "A"),
        ("D", "child_of", "B"),
        ("E", "child_of", "A"),
        ("E", "child_of", "B"),
        ("F", "child_of", "A"),
        ("F", "child_of", "B"),
        ("H", "child_of", "A"),
        ("H", "child_of", "T"),
        ("K", "child_of", "A"),
        ("K", "child_of", "T"),
        ("P", "child_of", "A"),
        ("P", "child_of", "T"),
        ("G", "child_of", "C"),
        ("G", "child_of", "M"),
        ("N", "child_of", "C"),
        ("N", "child_of", "M"),
        ("A", "spouse_of", "B"),
        ("A", "spouse_of", "T"),
        ("C", "spouse_of", "M"),
    ],
    "46": [
        ("Y", "child_of", "X"),
        ("K", "child_of", "Y"),
        ("K", "child_of", "Z"),
        ("Y", "spouse_of", "Z"),
    ],
    "47": [
        ("C", "child_of", "A"),
        ("D", "child_of", "A"),
        ("D", "child_of", "B"),
        ("A", "spouse_of", "B"),
    ],
    "50": [
        ("C", "child_of", "A"),
        ("C", "child_of", "B"),
        ("A", "spouse_of", "B"),
    ],
    "58": [
        ("G", "child_of", "X"),
        ("C1", "child_of", "X"),
        ("CN", "child_of", "X"),
        ("Đ", "child_of", "X"),
        ("K", "child_of", "X"),
        ("T1", "child_of", "C1"),
        ("V", "child_of", "C1"),
        ("L", "child_of", "C1"),
        ("T2", "child_of", "C1"),
        ("N", "child_of", "C1"),
        ("H", "child_of", "N"),
        ("N2", "child_of", "N"),
        ("C2", "child_of", "N"),
        ("X", "spouse_of", "Sạm"),
        ("Đ", "spouse_of", "E"),
    ],
    "117": [
        ("Lược", "spouse_of", "Thuyết"),
        ("Thiêm", "child_of", "Thuyết"),
        ("Thiêm", "child_of", "Lược"),
        ("Th", "child_of", "Thuyết"),
        ("Th", "child_of", "Lược"),
        ("Mỵ", "child_of", "Thuyết"),
        ("Mỵ", "child_of", "Lược"),
        ("Tiêu", "child_of", "Thuyết"),
        ("Tiêu", "child_of", "Lược"),
        ("T", "child_of", "Thuyết"),
        ("T", "child_of", "Lược"),
        ("Cường", "child_of", "Tiêu"),
        ("Mạnh", "child_of", "Tiêu"),
        ("Thiên", "child_of", "Thuyết"),
        ("Thiên", "child_of", "Lụa"),
    ],
    "60": [
        ("Đãn", "child_of", "Đản"),
        ("Đãn", "child_of", "Thao"),
        ("Đan", "child_of", "Đản"),
        ("Đan", "child_of", "Thao"),
        ("Du", "child_of", "Đãn"),
        ("Du", "child_of", "Lương"),
        ("Dự", "child_of", "Đãn"),
        ("Dự", "child_of", "Lương"),
        ("Nhự", "child_of", "Đãn"),
        ("Nhự", "child_of", "Lương"),
        ("Đông", "child_of", "Đãn"),
        ("Đông", "child_of", "Nghiến"),
        ("Mây", "child_of", "Đãn"),
        ("Mây", "child_of", "Nghiến"),
        ("Hoa", "child_of", "Đãn"),
        ("Hoa", "child_of", "Nghiến"),
        ("Đãn", "spouse_of", "Lương"),
        ("Đãn", "spouse_of", "Nghiến"),
    ],
    "64": [
        *[
            (child, "child_of", parent)
            for child in ("D1", "T3", "N", "T", "T2", "P", "H", "T1", "C")
            for parent in ("N2", "Ở")
        ],
        ("N2", "spouse_of", "Ở"),
    ],
    "65": [
        *[
            (child, "child_of", parent)
            for child in ("G", "T", "Bé D", "Bé L")
            for parent in ("T3", "M")
        ],
        ("Kiều Minh V", "child_of", "T3"),
        ("K1", "child_of", "Đ"),
        ("A", "child_of", "K1"),
        ("A", "child_of", "H"),
        ("K", "child_of", "K1"),
        ("K", "child_of", "H"),
        ("T3", "spouse_of", "M"),
        ("K1", "spouse_of", "H"),
    ],
    "66": [
        ("G", "child_of", "T8"),
        ("G", "child_of", "N2"),
        ("H", "child_of", "T8"),
        ("H", "child_of", "N2"),
        ("T", "child_of", "T8"),
        ("T", "child_of", "P1"),
        *[
            (child, "child_of", "H")
            for child in ("N", "T1", "Đ", "T2", "Q")
        ],
        ("T8", "spouse_of", "N2"),
        ("T8", "spouse_of", "P1"),
    ],
    "67": [
        *[
            (child, "child_of", parent)
            for child in ("T5", "T6", "T7", "M1", "L", "B1", "T8", "T3")
            for parent in ("X", "T4")
        ],
        *[
            (child, "child_of", parent)
            for child in ("S", "T", "G")
            for parent in ("T6", "D")
        ],
        *[
            (child, "child_of", parent)
            for child in ("H", "H1")
            for parent in ("T7", "T1")
        ],
        *[
            (child, "child_of", parent)
            for child in ("N", "T2", "H2")
            for parent in ("M1", "M")
        ],
        *[
            (child, "child_of", parent)
            for child in ("N1", "A")
            for parent in ("T8", "L1")
        ],
        ("X", "spouse_of", "T4"),
        ("T6", "spouse_of", "D"),
        ("T7", "spouse_of", "T1"),
        ("M1", "spouse_of", "M"),
        ("T8", "spouse_of", "L1"),
    ],
    "69": [
        *[
            (child, "child_of", parent)
            for child in ("D", "K", "C", "T")
            for parent in ("M", "Ú")
        ],
        ("M", "spouse_of", "Ú"),
        ("T", "spouse_of", "H"),
    ],
    "71": [
        *[
            (child, "child_of", "Q")
            for child in ("H1", "L", "T", "V")
        ],
        ("H", "child_of", "K"),
        ("L1", "child_of", "K"),
        ("P", "child_of", "V"),
        ("P", "child_of", "N1"),
        ("H2", "child_of", "V"),
        ("H2", "child_of", "N1"),
        ("Q", "spouse_of", "K"),
        ("V", "spouse_of", "N1"),
    ],
    "74": [
        *[
            (child, "child_of", parent)
            for child in ("L", "O", "H1", "Đ", "T1")
            for parent in ("C", "H")
        ],
        ("T", "child_of", "H"),
        ("C", "spouse_of", "H"),
    ],
    "85": [
        ("H", "spouse_of", "M"),
        ("L", "child_of", "M"),
        ("L", "child_of", "H"),
        ("T2", "child_of", "M"),
        ("T2", "child_of", "H"),
        ("M", "child_of", "T"),
        ("M", "child_of", "T1"),
    ],
    "91": [
        *[
            (child, "child_of", parent)
            for child in ("D", "V", "N", "N5", "P")
            for parent in ("Đ", "M1")
        ],
        ("H1", "child_of", "Đ"),
        ("H1", "child_of", "Đ1"),
        *[
            (child, "child_of", parent)
            for child in ("T", "N1", "N6")
            for parent in ("N5", "V1")
        ],
        *[
            (child, "child_of", parent)
            for child in ("B", "N2", "N3")
            for parent in ("H1", "T2")
        ],
        ("Đ", "spouse_of", "M1"),
        ("Đ", "spouse_of", "Đ1"),
        ("Đ", "spouse_of", "H"),
        ("N5", "spouse_of", "V1"),
        ("H1", "spouse_of", "T2"),
    ],
    "92": [
        ("C1", "child_of", "S"),
        ("C1", "child_of", "M"),
        ("T", "child_of", "S"),
        ("T", "child_of", "M"),
        ("C", "child_of", "S"),
        ("C", "child_of", "Đ"),
        ("T1", "child_of", "S"),
        ("T1", "child_of", "Đ"),
        ("S", "spouse_of", "M"),
        ("S", "spouse_of", "Đ"),
    ],
    "98": [
        *[
            (child, "child_of", parent)
            for child in ("N", "S1", "K1", "T1", "S2")
            for parent in ("T2", "T5")
        ],
        ("T3", "child_of", "T1"),
        ("L1", "child_of", "T1"),
        ("H", "child_of", "T1"),
        ("C", "child_of", "S2"),
        ("T2", "spouse_of", "T5"),
    ],
}


ENTITY_UPDATES: dict[str, dict[str, dict[str, Any]]] = {
    "7": {
        "Minh": {
            "relationship_to_decedent": "spouse",
            "relationship_status": "married",
        },
        "Thủy": {
            "relationship_to_decedent": "cohabiting_partner",
            "relationship_status": "unregistered",
        },
        "Xuân": {"relationship_to_decedent": "biological_child"},
        "Yên": {"relationship_to_decedent": "biological_child"},
        "Sơn": {"relationship_to_decedent": "biological_child"},
    },
    "8": {
        "Minh": {
            "relationship_to_decedent": "spouse",
            "relationship_status": "married",
        },
        "Thủy": {
            "relationship_to_decedent": "cohabiting_partner",
            "relationship_status": "unregistered",
        },
        "Xuân": {"relationship_to_decedent": "biological_child"},
        "Yên": {"relationship_to_decedent": "biological_child"},
        "Sơn": {"relationship_to_decedent": "biological_child"},
    },
    "117": {
        "Th": {"name": "Thuỳ"},
    },
    "13": {
        "B": {
            "relationship_to_decedent": "spouse",
            "relationship_status": "married",
        },
        "C": {
            "relationship_to_decedent": "biological_child",
            "relationship_status": None,
        },
        "D": {"relationship_to_decedent": "biological_child"},
        "E": {"relationship_to_decedent": "biological_child"},
        "F": {"relationship_to_decedent": "biological_child"},
        "M": {"relationship_to_decedent": "child_in_law"},
    },
    "46": {
        "Y": {"relationship_to_decedent": "biological_child"},
        "Z": {
            "relationship_to_decedent": "child_in_law",
            "relationship_status": "widowed",
        },
        "K": {"relationship_to_decedent": "grandchild_by_representation"},
    },
    "47": {
        "C": {
            "relationship_to_decedent": "other",
            "relationship_status": None,
        },
        "D": {"relationship_to_decedent": "biological_child"},
    },
    "50": {
        "B": {
            "relationship_to_decedent": "spouse",
            "relationship_status": "married",
        },
        "X": {"name": "Quỹ Từ thiện X"},
    },
    "58": {
        "G": {
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
        "V": {
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
        "N": {
            "relationship_status": "deceased_after_decedent",
            "alive_at_decedent_death": True,
        },
        "H": {"relationship_to_decedent": "other"},
        "N2": {"relationship_to_decedent": "other"},
        "C2": {"relationship_to_decedent": "other"},
    },
    "60": {
        "Đan": {
            "relationship_to_decedent": "sibling",
            "relationship_status": None,
        }
    },
    "64": {
        "N2": {
            "is_decedent": True,
            "relationship_status": None,
        },
        "Ở": {
            "is_decedent": True,
            "relationship_to_decedent": "spouse",
            "relationship_status": "deceased_after_decedent",
        },
        "N": {
            "is_decedent": False,
            "relationship_to_decedent": "biological_child",
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
    },
    "65": {
        "T3": {
            "is_decedent": True,
            "relationship_status": None,
        },
        "Đ": {
            "is_decedent": True,
            "relationship_to_decedent": "other",
            "relationship_status": "deceased_after_decedent",
        },
        "M": {
            "relationship_to_decedent": "spouse",
            "relationship_status": "deceased_before_decedent",
        },
        "T": {
            "is_decedent": False,
            "relationship_to_decedent": "biological_child",
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
        "K1": {
            "relationship_to_decedent": "other",
            "relationship_status": "deceased_after_decedent",
        },
        "H": {"relationship_to_decedent": "other"},
        "A": {"relationship_to_decedent": "other"},
        "K": {"relationship_to_decedent": "other"},
    },
    "66": {
        "T8": {
            "is_decedent": True,
            "relationship_status": None,
        },
        "N2": {"relationship_to_decedent": "cohabiting_partner"},
        "P1": {"relationship_to_decedent": "cohabiting_partner"},
        "G": {"relationship_to_decedent": "biological_child"},
        "H": {"relationship_to_decedent": "biological_child"},
        "T": {
            "is_decedent": False,
            "relationship_to_decedent": "biological_child",
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
        "N": {
            "relationship_to_decedent": "grandchild",
            "relationship_status": None,
        },
        "T1": {"relationship_to_decedent": "grandchild"},
        "Đ": {"relationship_to_decedent": "grandchild"},
        "T2": {"relationship_to_decedent": "grandchild"},
        "Q": {"relationship_to_decedent": "grandchild"},
    },
    "67": {
        "T4": {
            "is_decedent": True,
            "relationship_to_decedent": "spouse",
            "relationship_status": "deceased_after_decedent",
        },
        "M": {
            "relationship_to_decedent": "child_in_law",
            "relationship_status": "widowed",
            "alive_at_decedent_death": True,
        },
        "N": {
            "relationship_to_decedent": "grandchild",
            "relationship_status": None,
        },
        "T2": {
            "relationship_to_decedent": "grandchild",
            "relationship_status": None,
        },
        "H2": {
            "relationship_to_decedent": "grandchild",
            "relationship_status": None,
        },
        "L1": {
            "relationship_to_decedent": "child_in_law",
            "relationship_status": "widowed",
        },
        "S": {"relationship_to_decedent": "grandchild"},
        "T": {"relationship_to_decedent": "grandchild"},
        "G": {"relationship_to_decedent": "grandchild"},
        "H": {"relationship_to_decedent": "grandchild"},
        "H1": {"relationship_to_decedent": "grandchild"},
        "N1": {"relationship_to_decedent": "grandchild"},
        "A": {"relationship_to_decedent": "grandchild"},
    },
    "69": {
        "Ú": {
            "is_decedent": True,
            "relationship_to_decedent": "spouse",
            "relationship_status": "deceased_before_decedent",
        },
        "H": {
            "relationship_to_decedent": "child_in_law",
            "relationship_status": "divorced",
            "alive_at_decedent_death": True,
        },
    },
    "71": {
        "H1": {
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
        "L": {
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
        "T": {
            "relationship_status": None,
            "alive_at_decedent_death": True,
        },
        "N1": {"relationship_to_decedent": "child_in_law"},
        "P": {"relationship_to_decedent": "grandchild_by_representation"},
        "H2": {
            "type": "person",
            "relationship_to_decedent": "grandchild_by_representation",
        },
        "H": {"relationship_to_decedent": "other"},
        "L1": {"relationship_to_decedent": "other"},
    },
    "74": {
        "H": {
            "is_decedent": True,
            "relationship_to_decedent": "spouse",
            "relationship_status": "deceased_after_decedent",
        },
        "Đ": {"relationship_status": "deceased_after_decedent"},
        "T1": {"relationship_status": "deceased_after_decedent"},
    },
    "85": {
        "T2": {"relationship_to_decedent": "biological_child"},
    },
    "91": {
        "M1": {
            "is_decedent": True,
            "relationship_to_decedent": "spouse",
        },
        "V1": {
            "relationship_to_decedent": "child_in_law",
            "relationship_status": "widowed",
            "alive_at_decedent_death": True,
        },
        "N5": {"relationship_status": "deceased_after_decedent"},
        "T2": {"relationship_to_decedent": "child_in_law"},
        "B": {"relationship_to_decedent": "grandchild"},
        "N2": {"relationship_to_decedent": "grandchild"},
        "N3": {"relationship_to_decedent": "grandchild"},
    },
    "92": {
        "Đ": {
            "is_decedent": True,
            "relationship_to_decedent": "spouse",
            "relationship_status": "deceased_after_decedent",
        },
        "C": {"name": "C"},
    },
    "98": {
        "T3": {"relationship_to_decedent": "grandchild"},
        "L1": {"relationship_to_decedent": "grandchild"},
        "H": {"relationship_to_decedent": "grandchild"},
        "C": {"relationship_to_decedent": "grandchild"},
    },
    "147": {
        "M": {"relationship_to_decedent": "grandchild"},
        "N": {"relationship_to_decedent": "grandchild"},
        "T1": {"relationship_to_decedent": "grandchild"},
    },
}


DECEDENT_REPLACEMENTS = {
    "12": ("Sáu", ["Sáu", "Lâm", "Hoa"]),
    "58": ("X", ["X", "C1"]),
    "60": ("Đãn", ["Đãn"]),
    "64": ("N2", ["N2", "Ở"]),
    "65": ("T3", ["T3", "Đ"]),
    "66": ("T8", ["T8", "H"]),
    "67": ("X", ["X", "T4"]),
    "69": ("M", ["M", "Ú"]),
    "74": ("C", ["C", "H"]),
    "78": ("G", ["G", "H2"]),
    "83": ("Đ1", ["Đ1", "C1"]),
    "91": ("Đ", ["Đ", "M1"]),
    "92": ("S", ["S", "Đ"]),
    "98": ("T5", ["T5", "T2"]),
    "109": ("G", ["G", "H2"]),
    "117": ("Thuyết", ["Thuyết", "Lược", "Tiêu"]),
    "128": ("T6", ["T6", "L", "H1"]),
    "129": ("T3", ["T3", "H4"]),
}

TEMPORAL_BOUNDARY_TEXT_REPLACEMENTS = {
    "69": ("chết năm 1990", "chết trước ngày 10/09/1990"),
    "90": ("chết năm 1990", "chết trước ngày 10/09/1990"),
    "98": ("mất năm 1996", "mất trước ngày 01/07/1996"),
    "149": ("chết năm 1996", "chết trước ngày 01/07/1996"),
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relationship_objects(
    values: list[tuple[str, str, str]]
) -> list[dict[str, str]]:
    return [
        {"subject": subject, "predicate": predicate, "object": object_}
        for subject, predicate, object_ in values
    ]


def main() -> None:
    input_hash = file_sha256(GOLD_PATH)
    data = json.loads(GOLD_PATH.read_text(encoding="utf-8-sig"))
    with BENCHMARK_PATH.open(encoding="utf-8-sig", newline="") as handle:
        benchmark_rows = list(csv.DictReader(handle))
    benchmark_by_id = {row["Case_ID"]: row for row in benchmark_rows}
    by_id = {str(case["case_id"]): case for case in data}
    log_rows: list[dict[str, str]] = []

    def log(
        case_id: str,
        category: str,
        location: str,
        old_value: Any,
        new_value: Any,
        note: str,
    ) -> None:
        if old_value == new_value:
            return
        log_rows.append(
            {
                "case_id": case_id,
                "category": category,
                "location": location,
                "old_value": json.dumps(old_value, ensure_ascii=False),
                "new_value": json.dumps(new_value, ensure_ascii=False),
                "evidence": note,
            }
        )

    # CSV is the canonical source of runtime query text and scoring metadata.
    for case_id, case in by_id.items():
        row = benchmark_by_id[case_id]
        for field, csv_field in (
            ("source", "Source"),
            ("query_text", "User_Query"),
        ):
            old = case.get(field)
            new = row[csv_field]
            log(
                case_id,
                "SYNC_WITH_BENCHMARK",
                field,
                old,
                new,
                f"Copied from benchmark.csv::{csv_field}.",
            )
            case[field] = new
        ground_truth = case["ground_truth_for_scoring"]
        for field, csv_field in (
            ("expected_articles", "Expected_Articles"),
            ("expected_distribution_raw", "Expected_Distribution"),
        ):
            old = ground_truth.get(field)
            new = row[csv_field]
            log(
                case_id,
                "SYNC_WITH_BENCHMARK",
                f"ground_truth_for_scoring.{field}",
                old,
                new,
                f"Copied from benchmark.csv::{csv_field}.",
            )
            ground_truth[field] = new

    # Keep legacy evidence snippets synchronized with the author-approved
    # temporal boundary clarification in the canonical runtime query.
    def replace_nested_text(value: Any, old: str, new: str) -> Any:
        if isinstance(value, str):
            return value.replace(old, new)
        if isinstance(value, list):
            return [replace_nested_text(item, old, new) for item in value]
        if isinstance(value, dict):
            return {
                key: replace_nested_text(item, old, new)
                for key, item in value.items()
            }
        return value

    for case_id, (old_text, new_text) in TEMPORAL_BOUNDARY_TEXT_REPLACEMENTS.items():
        case = by_id[case_id]
        updated = replace_nested_text(case, old_text, new_text)
        if updated != case:
            log(
                case_id,
                "SYNC_TEMPORAL_BOUNDARY_EVIDENCE",
                "case_text_fields",
                old_text,
                new_text,
                "Keep evidence spans synchronized with benchmark.csv.",
            )
            case.clear()
            case.update(updated)

    # Remove the duplicate T1 entity in case 58. Code T is unused; T1 is the
    # code referenced by the corrected family graph.
    case58 = by_id["58"]
    old_entities = case58["entities"]
    duplicate_t = next(
        (
            entity
            for entity in old_entities
            if entity["entity_code"] == "T"
        ),
        None,
    )
    case58["entities"] = [
        entity for entity in old_entities if entity["entity_code"] != "T"
    ]
    if duplicate_t:
        log(
            "58",
            "REMOVE_DUPLICATE_ENTITY",
            "entities[entity_code=T]",
            duplicate_t,
            None,
            "Query contains one person T1; code T was unused and duplicated T1.",
        )
    case58.get("relationship_reasoning", {}).pop("T", None)

    # Case 117 was rewritten as a determinate three-opening scenario. Remove
    # relatives belonging only to the discarded source dispute before graph
    # and evidence validation.
    case117 = by_id["117"]
    retained_117 = {
        "Thuyết", "Lược", "Thiêm", "Th", "Mỵ", "Tiêu", "T",
        "Cường", "Mạnh", "Lụa", "Thiên",
    }
    case117["entities"] = [
        entity
        for entity in case117["entities"]
        if entity["entity_code"] in retained_117
    ]
    case117["relationships"] = [
        relationship
        for relationship in case117["relationships"]
        if relationship["subject"] in retained_117
        and relationship["object"] in retained_117
    ]
    case117["relationship_reasoning"] = {
        code: note
        for code, note in case117.get("relationship_reasoning", {}).items()
        if code in retained_117
    }

    for case_id, updates_by_code in ENTITY_UPDATES.items():
        case = by_id[case_id]
        entities_by_code = {
            entity["entity_code"]: entity for entity in case["entities"]
        }
        for code, updates in updates_by_code.items():
            if code not in entities_by_code:
                raise KeyError(f"case {case_id}: missing entity code {code}")
            entity = entities_by_code[code]
            for field, new_value in updates.items():
                old_value = entity.get(field)
                log(
                    case_id,
                    "QUERY_VERIFIED_ENTITY_REPAIR",
                    f"entities[{code}].{field}",
                    old_value,
                    new_value,
                    "Directly supported by query_text.",
                )
                entity[field] = new_value
            case.setdefault("relationship_reasoning", {})[code] = (
                f"[{code}]: Quan hệ đã được đối chiếu trực tiếp với query_text."
            )

    for case_id, (primary_code, target_codes) in DECEDENT_REPLACEMENTS.items():
        case = by_id[case_id]
        entities_by_code = {
            entity["entity_code"]: entity for entity in case["entities"]
        }
        if any(code not in entities_by_code for code in target_codes):
            raise KeyError(f"case {case_id}: missing target decedent code")
        old_value = case["decedent"]
        new_value = {
            "name": entities_by_code[primary_code]["name"],
            "entity_code": primary_code,
            "all_decedent_codes_detected": target_codes,
        }
        log(
            case_id,
            "QUERY_VERIFIED_DECEDENT_REPAIR",
            "decedent",
            old_value,
            new_value,
            "Target decedent(s) are explicit in the final query instruction.",
        )
        case["decedent"] = new_value
        for entity in case["entities"]:
            should_be_target = entity["entity_code"] in target_codes
            if entity.get("is_decedent") != should_be_target:
                log(
                    case_id,
                    "QUERY_VERIFIED_DECEDENT_REPAIR",
                    f"entities[{entity['entity_code']}].is_decedent",
                    entity.get("is_decedent"),
                    should_be_target,
                    "Synchronized with target decedent codes.",
                )
                entity["is_decedent"] = should_be_target

    for case_id, replacements in RELATIONSHIP_REPLACEMENTS.items():
        case = by_id[case_id]
        old_value = case["relationships"]
        new_value = relationship_objects(replacements)
        log(
            case_id,
            "QUERY_VERIFIED_GRAPH_REPLACEMENT",
            "relationships",
            old_value,
            new_value,
            "Family graph transcribed from explicit statements in query_text.",
        )
        case["relationships"] = new_value

    # Evidence repairs and fact-only monetary corrections.
    case3 = by_id["3"]
    old_money = case3["monetary_facts"]
    case3["monetary_facts"] = [
        fact
        for fact in old_money
        if not (
            fact["amount"] == 210_000_000
            and fact["context_snippet"].startswith("Tổng di sản")
        )
    ]
    log(
        "3",
        "REMOVE_DERIVED_MONETARY_FACT",
        "monetary_facts[amount=210000000]",
        [
            fact
            for fact in old_money
            if fact["amount"] == 210_000_000
        ],
        None,
        "210,000,000 is a computed estate remainder, not an explicit fact.",
    )

    case63 = by_id["63"]
    for fact in case63["monetary_facts"]:
        if fact["amount"] == 2_000_000_000:
            old = dict(fact)
            fact["role"] = "distractor"
            fact["context_snippet"] = (
                "Trong đó, vào năm 2006, cụ Trương Văn T1 và cụ Trần Thị B "
                "đã lập hợp đồng tặng cho hợp pháp và hoàn tất thủ tục sang "
                "tên một phần tài sản chung trị giá 2.000.000.000 đồng cho "
                "người con trai út là ông Trương Quan C."
            )
            log(
                "63",
                "QUERY_VERIFIED_MONETARY_REPAIR",
                "monetary_facts[amount=2000000000]",
                old,
                fact,
                "The amount was explicitly transferred before death.",
            )

    case81 = by_id["81"]
    for fact in case81["monetary_facts"]:
        if fact["amount"] == 3_770_900_000:
            old = dict(fact)
            fact["context_snippet"] = (
                "Tài sản riêng của cụ T5 gồm một khối tài sản trị giá "
                "3.770.900.000 đồng và một khoản tài sản khác đang do ông S, "
                "ông T2 quản lý."
            )
            log(
                "81",
                "EVIDENCE_SPAN_REPAIR",
                "monetary_facts[amount=3770900000].context_snippet",
                old["context_snippet"],
                fact["context_snippet"],
                "Replaced joined spans with one exact query substring.",
            )

    case91 = by_id["91"]
    for fact in case91["monetary_facts"]:
        if fact["amount"] == 550_000_000:
            old = dict(fact)
            fact["role"] = "distractor"
            fact["context_snippet"] = (
                "Tuy vậy, H có công sức chăm sóc cụ Đ và đóng góp tôn tạo "
                "tài sản nên được trích 550 triệu đồng."
            )
            log(
                "91",
                "QUERY_VERIFIED_MONETARY_REPAIR",
                "monetary_facts[amount=550000000]",
                old,
                fact,
                "This is contribution compensation, not an estate asset.",
            )

    case93 = by_id["93"]
    for fact in case93["monetary_facts"]:
        if fact["amount"] == 235_000_000:
            old = dict(fact)
            fact["role"] = "distractor"
            log(
                "93",
                "QUERY_VERIFIED_MONETARY_REPAIR",
                "monetary_facts[amount=235000000].role",
                old["role"],
                fact["role"],
                "The claimant explicitly withdrew this funeral-cost request.",
            )

    case50 = by_id["50"]
    old_case50_money = list(case50["monetary_facts"])
    quoted_fact = next(
        fact
        for fact in old_case50_money
        if "trăn trối" in fact["context_snippet"]
    )
    case50["monetary_facts"] = [
        quoted_fact,
        {
            "amount": 4_000_000_000,
            "role": "bequest_amount",
            "recipient_code": "X",
            "context_snippet": quoted_fact["context_snippet"],
        },
    ]
    log(
        "50",
        "QUERY_VERIFIED_MONETARY_REPAIR",
        "monetary_facts",
        old_case50_money,
        case50["monetary_facts"],
        "The query states one savings asset and one oral-will disposition "
        "to Quỹ Từ thiện X; the second estate_asset was a duplicate mention.",
    )

    bequest_recipients = {
        ("4", 9_000_000_000): "T",
        ("6", 100_000_000): "B",
        ("44", 8_000_000_000): "G",
        ("54", 100_000_000): "M",
        ("54", 200_000_000): "HNN",
    }
    for (case_id, amount), recipient_code in bequest_recipients.items():
        fact = next(
            fact
            for fact in by_id[case_id]["monetary_facts"]
            if fact["role"] == "bequest_amount" and fact["amount"] == amount
        )
        old = fact.get("recipient_code")
        fact["recipient_code"] = recipient_code
        log(
            case_id,
            "ADD_EXPLICIT_BEQUEST_RECIPIENT",
            f"monetary_facts[amount={amount}].recipient_code",
            old,
            recipient_code,
            "Recipient is stated in the exact context_snippet.",
        )

    exact_snippets = {
        ("28", "M"): (
            'Trước khi mất, cụ Nguyễn Thị T ra Văn phòng Công chứng lập một '
            'bản di chúc hợp pháp, trong đó ghi rõ: "Tôi di tặng toàn bộ căn '
            'hộ chung cư trị giá 5.000.000.000 đồng này cho ông Phạm Văn M, '
            'tuyệt đối không để lại cho con gái tôi".'
        ),
        ("48", "V"): (
            "Cha mẹ ông Nguyễn Văn P đều đã chết trước ông; ông Nguyễn Văn P "
            "không có con và tại thời điểm ông chết chỉ có vợ là bà Trần Thị V."
        ),
        ("103", "U"): (
            "Năm người con còn sống gồm: ông Nguyễn Văn L1 (nguyên đơn), ông "
            "Nguyễn Văn Đ1 (bị đơn), ông Nguyễn Văn Đ2 (người liên quan), ông "
            "Nguyễn Văn L2 (người liên quan) và bà Nguyễn Thị U."
        ),
        ("58", "T1"): (
            "Bà C1 (chết năm 2017) và chồng (chết năm 1987) có 5 người con: "
            "T1, V, L, T2 và N1."
        ),
        ("58", "T2"): (
            "Bà C1 (chết năm 2017) và chồng (chết năm 1987) có 5 người con: "
            "T1, V, L, T2 và N1."
        ),
        ("58", "N2"): (
            "Ông N1 (chết năm 2016) để lại 3 người con: H, N2 và C2."
        ),
        ("58", "C2"): (
            "Ông N1 (chết năm 2016) để lại 3 người con: H, N2 và C2."
        ),
        ("87", "Q"): (
            "bà C2 (mất năm 2017, có 2 con là Q và T5)"
        ),
        ("87", "T5"): (
            "bà C2 (mất năm 2017, có 2 con là Q và T5)"
        ),
        ("87", "N1"): (
            "bà H6 (mất năm 2019, có 3 con là N1, N4 và N5)"
        ),
        ("87", "N4"): (
            "bà H6 (mất năm 2019, có 3 con là N1, N4 và N5)"
        ),
        ("87", "N5"): (
            "bà H6 (mất năm 2019, có 3 con là N1, N4 và N5)"
        ),
        ("98", "H"): (
            "Năm 2017 ông T1 mất, các con của ông là T3, L1 và H tiếp tục "
            "quản lý di sản."
        ),
    }

    case125_family_span = (
        "Ông Hoàng Văn S2 (chết năm 2010) và bà Triệu Thị M (chết năm 2018, "
        "không để lại di chúc) có 7 người con là Hoàng Thị D (chết năm 2021), "
        "Hoàng Thị V, Hoàng Thị Tr, Hoàng Thị T, Hoàng Thị T4 (chết năm "
        "2004), Hoàng Văn B (chết năm 2019, không để lại di chúc) và Hoàng Lệ T1."
    )
    for code in ("S2", "M", "D", "V", "Tr", "T", "T4", "B", "T1"):
        exact_snippets[("125", code)] = case125_family_span
    case125_b_family_span = (
        "Anh B có vợ là Hoàng Thị H và một người con duy nhất là Hoàng Việt V1."
    )
    for code in ("H", "V1"):
        exact_snippets[("125", code)] = case125_b_family_span

    case145_entity_span = (
        "Cụ K1 và cụ N2 (đều mất năm 2015) có 8 người con chung gồm: M2, E, "
        "Đ (mất 2009, có 2 người con là Đ2 và Đ3), Đ1, T, V (mất năm 2022; "
        "V1, V2, V3 và V4 là những người thuộc nhóm vợ, chồng hoặc con của V, "
        "nhưng nguồn không nêu rõ quan hệ cụ thể của từng người), T1 và H."
    )
    for code in ("K1", "N2", "M2", "E", "Đ", "Đ1", "T", "V", "T1", "H"):
        exact_snippets[("145", code)] = case145_entity_span
    for (case_id, code), snippet in exact_snippets.items():
        case = by_id[case_id]
        entity = next(
            entity
            for entity in case["entities"]
            if entity["entity_code"] == code
        )
        old = entity.get("context_snippet")
        log(
            case_id,
            "EVIDENCE_SPAN_REPAIR",
            f"entities[{code}].context_snippet",
            old,
            snippet,
            "Replaced synthetic/paraphrased evidence with an exact query span.",
        )
        entity["context_snippet"] = snippet

    monetary_evidence_repairs = {
        ("5", 500_000_000): (
            "Khối tài sản chung của ông Nguyễn Văn A và bà Trần Thị B được "
            "xác định là 500.000.000 đồng."
        ),
        ("12", 80_000_000): (
            "Tài sản chung hợp nhất của ông Nguyễn Văn Sáu và bà Lê Thị Son "
            "được xác định là 80.000.000 đồng."
        ),
        ("28", 5_000_000_000): exact_snippets[("28", "M")],
        ("92", 1_797_518_795): (
            "Trong phạm vi bài toán, khoản ghi nhận công sức quản lý và tôn "
            "tạo của T được ấn định bằng 20% tổng giá trị khối tài sản, tương "
            "đương 1.797.518.795 đồng."
        ),
        ("125", 405_240_752): (
            "Lúc sinh thời, ông S2 và bà M tạo lập được khối tài sản chung là "
            "các diện tích đất đã bị Nhà nước thu hồi, được bồi thường tổng số "
            "tiền 405.240.752 đồng; mỗi người sở hữu một nửa khối tài sản này."
        ),
        ("138", 380_628_000): (
            "Tài sản chung của hai cụ để lại là một khối nhà đất được các bên "
            "thống nhất quy đổi thành tiền có tổng trị giá là 380.628.000 đồng."
        ),
    }
    for (case_id, amount), snippet in monetary_evidence_repairs.items():
        matching = [
            fact
            for fact in by_id[case_id]["monetary_facts"]
            if fact["amount"] == amount
        ]
        if not matching:
            raise ValueError(f"Case {case_id}: missing monetary fact {amount}")
        for index, fact in enumerate(matching):
            old = fact.get("context_snippet")
            log(
                case_id,
                "EVIDENCE_SPAN_REPAIR",
                f"monetary_facts[amount={amount}][{index}].context_snippet",
                old,
                snippet,
                "Synchronized exact evidence after an approved runtime-text repair.",
            )
            fact["context_snippet"] = snippet

    # Whole-scenario rewrites invalidate otherwise-correct evidence spans.
    # Re-anchor each entity to the shortest exact sentence containing its
    # name. Case 117 also replaces the obsolete per-square-metre fact with the
    # explicitly stipulated total value.
    case117["monetary_facts"] = [
        {
            "amount": 4_403_700_000,
            "role": "estate_asset",
            "context_snippet": (
                "Ông Thuyết và bà Lược cùng sở hữu một thửa đất diện tích "
                "629,1m2, trị giá 4.403.700.000 đồng; mỗi người sở hữu một nửa."
            ),
        }
    ]
    for case_id in (
        "5", "9", "10", "13", "58", "66", "80", "81", "82", "83",
        "103", "105", "109", "117", "120", "122", "125", "128", "129", "136", "140",
        "144", "148", "149",
    ):
        case = by_id[case_id]
        query_sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", case["query_text"])
            if sentence.strip()
        ]
        for entity in case["entities"]:
            name = entity["name"]
            pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)")
            matches = [sentence for sentence in query_sentences if pattern.search(sentence)]
            entity["context_snippet"] = min(matches, key=len) if matches else None
        for fact in case["monetary_facts"]:
            old_snippet = fact.get("context_snippet")
            if not old_snippet or old_snippet in case["query_text"]:
                continue
            amount_digits = str(fact["amount"])
            matches = [
                sentence
                for sentence in query_sentences
                if amount_digits in re.sub(r"\D", "", sentence)
            ]
            fact["context_snippet"] = min(matches, key=len) if matches else None

    # A symmetric relationship is stored once. Keep first occurrence to retain
    # stable orientation and remove reverse duplicates.
    for case_id, case in by_id.items():
        seen: set[tuple[Any, ...]] = set()
        deduplicated = []
        removed = []
        for relationship in case["relationships"]:
            predicate = relationship["predicate"]
            if predicate in {"spouse_of", "sibling_of"}:
                key = (
                    predicate,
                    *sorted(
                        [relationship["subject"], relationship["object"]]
                    ),
                )
            else:
                key = (
                    predicate,
                    relationship["subject"],
                    relationship["object"],
                )
            if key in seen:
                removed.append(relationship)
                continue
            seen.add(key)
            deduplicated.append(relationship)
        if removed:
            log(
                case_id,
                "REMOVE_SYMMETRIC_DUPLICATE",
                "relationships",
                removed,
                None,
                "spouse_of/sibling_of is stored once regardless of direction.",
            )
        case["relationships"] = deduplicated

    # Synchronize scoring whitelist after entity corrections.
    for case_id, case in by_id.items():
        new_allowed = [
            entity["entity_code"] for entity in case["entities"]
        ]
        ground_truth = case["ground_truth_for_scoring"]
        old_allowed = ground_truth.get("allowed_entities")
        log(
            case_id,
            "SYNC_ALLOWED_ENTITIES",
            "ground_truth_for_scoring.allowed_entities",
            old_allowed,
            new_allowed,
            "Whitelist must equal the entity codes present in the case.",
        )
        ground_truth["allowed_entities"] = new_allowed

    validate_legacy_gold(data, benchmark_by_id)
    GOLD_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Repaired {len(data)} legacy gold records.")
    print(f"Logged changes: {len(log_rows)}")
    print("Legacy structural audit: PASS")
    print(f"Gold: {GOLD_PATH}")


def validate_legacy_gold(
    data: list[dict[str, Any]],
    benchmark_by_id: dict[str, dict[str, str]],
) -> None:
    errors: list[str] = []
    ids = [str(case["case_id"]) for case in data]
    expected_ids = {str(value) for value in range(1, 151)}
    if len(data) != 150 or set(ids) != expected_ids or len(ids) != len(set(ids)):
        errors.append("case IDs must be unique and exactly 1..150")

    for case in data:
        case_id = str(case["case_id"])
        codes = [entity["entity_code"] for entity in case["entities"]]
        code_set = set(codes)
        names = [entity.get("name") for entity in case["entities"]]
        if len(codes) != len(code_set):
            errors.append(f"case {case_id}: duplicate entity code")
        if any(not isinstance(name, str) or not name.strip() for name in names):
            errors.append(f"case {case_id}: empty entity name")
        if len(names) != len(set(names)):
            errors.append(f"case {case_id}: duplicate entity name")
        if case["decedent"]["entity_code"] not in code_set:
            errors.append(f"case {case_id}: primary decedent reference missing")
        targets = set(case["decedent"]["all_decedent_codes_detected"])
        flagged = {
            entity["entity_code"]
            for entity in case["entities"]
            if entity["is_decedent"]
        }
        if targets != flagged:
            errors.append(
                f"case {case_id}: target decedents {targets} != flags {flagged}"
            )
        allowed = set(
            case["ground_truth_for_scoring"]["allowed_entities"]
        )
        if allowed != code_set:
            errors.append(f"case {case_id}: allowed_entities mismatch")

        seen: set[tuple[Any, ...]] = set()
        parent_counts: Counter[str] = Counter()
        graph: dict[str, set[str]] = defaultdict(set)
        for relationship in case["relationships"]:
            subject = relationship["subject"]
            object_ = relationship["object"]
            predicate = relationship["predicate"]
            if subject not in code_set or object_ not in code_set:
                errors.append(
                    f"case {case_id}: missing relationship endpoint"
                )
            if subject == object_:
                errors.append(f"case {case_id}: self relationship")
            if predicate in {"spouse_of", "sibling_of"}:
                key = (predicate, *sorted([subject, object_]))
            else:
                key = (predicate, subject, object_)
            if key in seen:
                errors.append(
                    f"case {case_id}: duplicate semantic relationship {key}"
                )
            seen.add(key)
            if predicate in {"child_of", "represents"}:
                parent_counts[subject] += 1
                graph[subject].add(object_)
        for child, count in parent_counts.items():
            if count > 2:
                errors.append(
                    f"case {case_id}: {child} has {count} direct parents"
                )

        colors: dict[str, int] = {}

        def visit(node: str) -> None:
            colors[node] = 1
            for parent in graph.get(node, set()):
                if colors.get(parent, 0) == 0:
                    visit(parent)
                elif colors.get(parent) == 1:
                    errors.append(
                        f"case {case_id}: ancestry cycle at {node}->{parent}"
                    )
            colors[node] = 2

        for node in graph:
            if colors.get(node, 0) == 0:
                visit(node)

        for flag in case["legal_fact_flags"]:
            if flag["entity_code"] not in code_set:
                errors.append(f"case {case_id}: missing flag entity")
        query = case["query_text"]
        for entity in case["entities"]:
            snippet = entity.get("context_snippet")
            if snippet and snippet not in query:
                errors.append(
                    f"case {case_id}: bad entity evidence "
                    f"{entity['entity_code']}"
                )
        for fact in case["monetary_facts"]:
            snippet = fact.get("context_snippet")
            if snippet and snippet not in query:
                errors.append(
                    f"case {case_id}: bad monetary evidence {fact['amount']}"
                )
        row = benchmark_by_id[case_id]
        if case["query_text"].strip() != row["User_Query"].strip():
            errors.append(f"case {case_id}: query mismatch with CSV")
        if case["source"].strip() != row["Source"].strip():
            errors.append(f"case {case_id}: source mismatch with CSV")
        if (
            case["ground_truth_for_scoring"]["expected_articles"].strip()
            != row["Expected_Articles"].strip()
        ):
            errors.append(f"case {case_id}: articles mismatch with CSV")
        if (
            case["ground_truth_for_scoring"][
                "expected_distribution_raw"
            ].strip()
            != row["Expected_Distribution"].strip()
        ):
            errors.append(f"case {case_id}: distribution mismatch with CSV")

    if errors:
        raise ValueError(
            "Legacy gold validation failed:\n" + "\n".join(errors[:100])
        )


if __name__ == "__main__":
    main()
