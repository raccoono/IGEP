"""Evaluate extractor predictions against the full IGEP schema v2.2 gold.

Default protocol:
- evaluate every case in the gold file (150/150 for the current benchmark);
- do not filter cases using the repair log;
- report separate metrics for each schema component;
- report both structure metrics (including null/unknown/empty values) and
  content metrics (excluding placeholders).

The evaluator accepts either a JSON array or JSONL prediction file and writes a
machine-readable JSON report plus a Markdown summary.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from build_gold import graph_validation_errors, validate_instance


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = (
    PROJECT_ROOT
    / "data"
    / "canonical"
    / "gold.json"
)
DEFAULT_SCHEMA = PROJECT_ROOT / "schema" / "valid.md"
DEFAULT_SPLIT_MANIFEST = PROJECT_ROOT / "data" / "release" / "split.csv"
DEFAULT_JSON_REPORT = PROJECT_ROOT / "data" / "eval" / "full_schema_eval.json"
DEFAULT_MD_REPORT = PROJECT_ROOT / "data" / "eval" / "full_schema_eval.md"

GROUP_ORDER = [
    "target_decedents",
    "persons",
    "organizations",
    "relationships",
    "estates",
    "assets",
    "obligations",
    "wills",
    "dispositions",
    "inheritance_actions",
    "conduct_events",
    "agreements",
    "events",
    "legal_assertions",
]

GROUP_LABELS = {
    "target_decedents": "Target decedents",
    "persons": "Persons",
    "organizations": "Organizations",
    "relationships": "Relationships",
    "estates": "Estates",
    "assets": "Assets",
    "obligations": "Obligations",
    "wills": "Wills",
    "dispositions": "Will dispositions",
    "inheritance_actions": "Inheritance actions",
    "conduct_events": "Conduct events",
    "agreements": "Agreements",
    "events": "Events",
    "legal_assertions": "Legal assertions",
}

OWN_ID_KEYS = {
    "estate_id",
    "asset_id",
    "obligation_id",
    "will_id",
    "disposition_id",
    "action_id",
    "conduct_event_id",
    "agreement_id",
    "event_id",
    "assertion_id",
}
SINGLE_REFERENCE_KEYS = {
    "other_will_id",
    "related_estate_id",
    "related_asset_id",
    "related_will_id",
    "subject_ref",
}
LIST_REFERENCE_KEYS = {
    "asset_ids",
    "secured_asset_ids",
    "affected_asset_ids",
}
SYMMETRIC_RELATIONS = {"spouse_of", "sibling_of"}
CONTENT_PLACEHOLDERS = {
    "",
    "unknown",
    "not_mentioned",
}


def normalize_string(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def natural_case_key(case_id: str) -> tuple[int, int | str]:
    return (0, int(case_id)) if case_id.isdigit() else (1, case_id)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError(f"{path}: empty file")
    if text.lstrip().startswith("["):
        value = json.loads(text)
    else:
        value = [
            json.loads(line)
            for line_number, line in enumerate(text.splitlines(), start=1)
            if line.strip()
        ]
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a JSON array or JSONL records")
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValueError(f"{path}: record {index} is not an object")
        if "case_id" not in record:
            raise ValueError(f"{path}: record {index} has no case_id")
    return value


def index_records(
    records: Iterable[dict[str, Any]], path: Path
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        case_id = str(record["case_id"])
        if case_id in indexed:
            raise ValueError(f"{path}: duplicate case_id={case_id}")
        indexed[case_id] = record
    return indexed


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def reference_map(case: dict[str, Any]) -> dict[str, str]:
    """Map local technical IDs to stable semantic references."""

    references: dict[str, str] = {}
    for estate in safe_list(case.get("estates")):
        if not isinstance(estate, dict):
            continue
        decedent = normalize_string(str(estate.get("decedent", "")))
        estate_ref = f"estate::{decedent}"
        if isinstance(estate.get("estate_id"), str):
            references[estate["estate_id"]] = estate_ref

        for asset in safe_list(estate.get("assets")):
            if not isinstance(asset, dict) or not isinstance(
                asset.get("asset_id"), str
            ):
                continue
            fingerprint = stable_json(
                [
                    decedent,
                    normalize_string(str(asset.get("asset_type", ""))),
                    normalize_string(str(asset.get("description", ""))),
                    asset.get("value"),
                    normalize_string(str(asset.get("currency", ""))),
                ]
            )
            references[asset["asset_id"]] = f"asset::{fingerprint}"

        for obligation in safe_list(estate.get("obligations")):
            if not isinstance(obligation, dict) or not isinstance(
                obligation.get("obligation_id"), str
            ):
                continue
            fingerprint = stable_json(
                [
                    decedent,
                    normalize_string(str(obligation.get("obligation_type", ""))),
                    normalize_string(str(obligation.get("creditor", ""))),
                    obligation.get("amount"),
                ]
            )
            references[obligation["obligation_id"]] = (
                f"obligation::{fingerprint}"
            )

    for will in safe_list(case.get("wills")):
        if not isinstance(will, dict):
            continue
        will_ref = stable_json(
            [
                normalize_string(str(will.get("testator", ""))),
                will.get("date"),
            ]
        )
        if isinstance(will.get("will_id"), str):
            references[will["will_id"]] = f"will::{will_ref}"
        for disposition in safe_list(will.get("dispositions")):
            if not isinstance(disposition, dict) or not isinstance(
                disposition.get("disposition_id"), str
            ):
                continue
            disposition_ref = stable_json(
                [
                    will_ref,
                    normalize_string(
                        str(disposition.get("disposition_type", ""))
                    ),
                    normalize_string(str(disposition.get("recipient", ""))),
                    disposition.get("amount"),
                    disposition.get("share_ratio"),
                ]
            )
            references[disposition["disposition_id"]] = (
                f"disposition::{disposition_ref}"
            )

    for top_level_key in (
        "inheritance_actions",
        "conduct_events",
        "agreements",
        "events",
        "legal_assertions",
    ):
        for item in safe_list(case.get(top_level_key)):
            if not isinstance(item, dict):
                continue
            for id_key in OWN_ID_KEYS:
                if isinstance(item.get(id_key), str):
                    semantic = {
                        key: value
                        for key, value in item.items()
                        if key not in OWN_ID_KEYS
                    }
                    references[item[id_key]] = (
                        f"{top_level_key}::{stable_json(semantic)}"
                    )
    return references


def normalize_value(
    value: Any,
    references: dict[str, str],
    *,
    parent_key: str | None = None,
) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if key in OWN_ID_KEYS:
                continue
            child = value[key]
            if key in SINGLE_REFERENCE_KEYS and isinstance(child, str):
                child = references.get(child, child)
            elif key in LIST_REFERENCE_KEYS and isinstance(child, list):
                child = [
                    references.get(item, item) if isinstance(item, str) else item
                    for item in child
                ]
            result[key] = normalize_value(child, references, parent_key=key)
        return result
    if isinstance(value, list):
        normalized = [
            normalize_value(item, references, parent_key=parent_key)
            for item in value
        ]
        return sorted(normalized, key=stable_json)
    if isinstance(value, str):
        return normalize_string(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def normalized_relationship(
    relationship: dict[str, Any], references: dict[str, str]
) -> dict[str, Any]:
    value = dict(relationship)
    relation = normalize_string(str(value.get("relation", "")))
    subject = normalize_string(str(value.get("subject", "")))
    object_ = normalize_string(str(value.get("object", "")))
    if relation in SYMMETRIC_RELATIONS and object_ < subject:
        value["subject"], value["object"] = value.get("object"), value.get(
            "subject"
        )
    return normalize_value(value, references)


def invalid_record_identity(group: str, value: Any) -> str:
    return stable_json([group, "__invalid__", normalize_value(value, {})])


def group_records(
    case: dict[str, Any], group: str
) -> list[tuple[str, Any]]:
    """Return (stable identity, normalized record) pairs for one metric group."""

    refs = reference_map(case)
    records: list[tuple[str, Any]] = []

    def add(identity_parts: Any, record: Any) -> None:
        identity = stable_json(normalize_value(identity_parts, refs))
        records.append((identity, normalize_value(record, refs)))

    if group == "target_decedents":
        for value in safe_list(case.get("target_decedents")):
            add(["target_decedent", value], {"name": value})
        return records

    if group in {"persons", "organizations"}:
        for item in safe_list(case.get(group)):
            if not isinstance(item, dict):
                records.append((invalid_record_identity(group, item), item))
                continue
            add([group, item.get("name")], item)
        return records

    if group == "relationships":
        for item in safe_list(case.get("relationships")):
            if not isinstance(item, dict):
                records.append((invalid_record_identity(group, item), item))
                continue
            normalized = normalized_relationship(item, refs)
            add(
                [
                    group,
                    normalized.get("subject"),
                    normalized.get("relation"),
                    normalized.get("object"),
                ],
                normalized,
            )
        return records

    if group == "estates":
        for estate in safe_list(case.get("estates")):
            if not isinstance(estate, dict):
                records.append((invalid_record_identity(group, estate), estate))
                continue
            record = {
                key: value
                for key, value in estate.items()
                if key not in {"assets", "obligations"}
            }
            add([group, estate.get("decedent")], record)
        return records

    if group in {"assets", "obligations"}:
        for estate in safe_list(case.get("estates")):
            if not isinstance(estate, dict):
                continue
            decedent = estate.get("decedent")
            for item in safe_list(estate.get(group)):
                if not isinstance(item, dict):
                    records.append((invalid_record_identity(group, item), item))
                    continue
                record = {"estate_decedent": decedent, **item}
                if group == "assets":
                    if item.get("value") is not None:
                        identity = [
                            group,
                            decedent,
                            item.get("asset_type"),
                            item.get("value"),
                            item.get("currency"),
                        ]
                    else:
                        identity = [
                            group,
                            decedent,
                            item.get("asset_type"),
                            item.get("description"),
                        ]
                else:
                    identity = [
                        group,
                        decedent,
                        item.get("obligation_type"),
                        item.get("creditor"),
                    ]
                add(identity, record)
        return records

    if group == "wills":
        for will in safe_list(case.get("wills")):
            if not isinstance(will, dict):
                records.append((invalid_record_identity(group, will), will))
                continue
            record = {
                key: value
                for key, value in will.items()
                if key != "dispositions"
            }
            add([group, will.get("testator"), will.get("date")], record)
        return records

    if group == "dispositions":
        for will in safe_list(case.get("wills")):
            if not isinstance(will, dict):
                continue
            testator = will.get("testator")
            for item in safe_list(will.get("dispositions")):
                if not isinstance(item, dict):
                    records.append((invalid_record_identity(group, item), item))
                    continue
                record = {"testator": testator, **item}
                add(
                    [
                        group,
                        testator,
                        item.get("disposition_type"),
                        item.get("recipient"),
                        item.get("scope"),
                    ],
                    record,
                )
        return records

    top_level_identity_fields = {
        "inheritance_actions": ("person", "related_decedent", "action"),
        "conduct_events": ("actor", "target", "conduct_type"),
        "agreements": ("agreement_type", "participants"),
        "events": (
            "event_type",
            "person",
            "related_person",
            "time",
        ),
        "legal_assertions": (
            "subject_type",
            "subject_ref",
            "assertion",
        ),
    }
    if group in top_level_identity_fields:
        for item in safe_list(case.get(group)):
            if not isinstance(item, dict):
                records.append((invalid_record_identity(group, item), item))
                continue
            add(
                [group]
                + [item.get(field) for field in top_level_identity_fields[group]],
                item,
            )
        return records

    raise KeyError(f"Unknown metric group: {group}")


def flatten_facts(
    value: Any,
    *,
    content_only: bool,
    path: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], str]]:
    facts: list[tuple[tuple[str, ...], str]] = []
    if isinstance(value, dict):
        if not value:
            if not content_only:
                facts.append((path, "<empty-object>"))
            return facts
        for key in sorted(value):
            facts.extend(
                flatten_facts(
                    value[key],
                    content_only=content_only,
                    path=path + (key,),
                )
            )
        return facts
    if isinstance(value, list):
        if not value:
            if not content_only:
                facts.append((path, "<empty-list>"))
            return facts
        for item in value:
            facts.extend(
                flatten_facts(
                    item,
                    content_only=content_only,
                    path=path + ("[]",),
                )
            )
        return facts

    if content_only and (
        value is None
        or (
            isinstance(value, str)
            and normalize_string(value) in CONTENT_PLACEHOLDERS
        )
    ):
        return facts
    facts.append((path, stable_json(value)))
    return facts


def record_item_counter(records: list[tuple[str, Any]]) -> Counter[str]:
    return Counter(identity for identity, _ in records)


def record_fact_counter(
    records: list[tuple[str, Any]], *, content_only: bool
) -> Counter[str]:
    result: Counter[str] = Counter()
    for identity, record in records:
        for path, value in flatten_facts(record, content_only=content_only):
            result[stable_json([identity, list(path), value])] += 1
    return result


def counter_metrics(
    gold: Counter[str],
    prediction: Counter[str],
    *,
    empty_is_perfect: bool = False,
) -> dict[str, int | float | None]:
    true_positive = sum((gold & prediction).values())
    gold_count = sum(gold.values())
    predicted_count = sum(prediction.values())
    false_positive = predicted_count - true_positive
    false_negative = gold_count - true_positive

    if gold_count == 0 and predicted_count == 0:
        value = 1.0 if empty_is_perfect else None
        return {
            "gold": 0,
            "predicted": 0,
            "true_positive": 0,
            "false_positive": 0,
            "false_negative": 0,
            "precision": value,
            "recall": value,
            "f1": value,
        }

    precision = (
        true_positive / predicted_count if predicted_count else 0.0
    )
    recall = true_positive / gold_count if gold_count else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "gold": gold_count,
        "predicted": predicted_count,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def merge_counter(
    destination: Counter[str], source: Counter[str], prefix: str
) -> None:
    for key, count in source.items():
        destination[stable_json([prefix, key])] += count


def monetary_counter(case: dict[str, Any]) -> Counter[str]:
    """Return semantic context + exact monetary value pairs."""

    result: Counter[str] = Counter()
    refs = reference_map(case)

    def add(context: Any, value: Any) -> None:
        if value is None:
            return
        result[
            stable_json(
                [
                    normalize_value(context, refs),
                    normalize_value(value, refs),
                ]
            )
        ] += 1

    for estate in safe_list(case.get("estates")):
        if not isinstance(estate, dict):
            continue
        decedent = estate.get("decedent")
        for asset in safe_list(estate.get("assets")):
            if isinstance(asset, dict):
                add(
                    [
                        "asset",
                        decedent,
                        asset.get("asset_type"),
                        asset.get("description"),
                    ],
                    asset.get("value"),
                )
        for obligation in safe_list(estate.get("obligations")):
            if isinstance(obligation, dict):
                add(
                    [
                        "obligation",
                        decedent,
                        obligation.get("obligation_type"),
                        obligation.get("creditor"),
                    ],
                    obligation.get("amount"),
                )
    for will in safe_list(case.get("wills")):
        if not isinstance(will, dict):
            continue
        for disposition in safe_list(will.get("dispositions")):
            if isinstance(disposition, dict):
                add(
                    [
                        "disposition",
                        will.get("testator"),
                        disposition.get("disposition_type"),
                        disposition.get("recipient"),
                        disposition.get("scope"),
                    ],
                    disposition.get("amount"),
                )
    return result


def life_status_pairs(case: dict[str, Any]) -> dict[str, Any]:
    refs = reference_map(case)
    result: dict[str, Any] = {}
    for person in safe_list(case.get("persons")):
        if not isinstance(person, dict):
            continue
        name = stable_json(normalize_value(person.get("name"), refs))
        result[name] = normalize_value(person.get("life_status"), refs)
    return result


def schema_errors_for_case(
    case: dict[str, Any] | None,
    schema: dict[str, Any],
) -> tuple[list[str], list[str]]:
    if case is None:
        return ["missing prediction record"], ["missing prediction record"]
    structural = validate_instance(case, schema, schema)
    try:
        graph = graph_validation_errors(case)
    except (KeyError, TypeError, AttributeError) as error:
        graph = [f"graph validation unavailable: {error}"]
    return structural, graph


def evaluate(
    gold_records: list[dict[str, Any]],
    prediction_records: list[dict[str, Any]],
    schema: dict[str, Any],
    *,
    gold_path: Path,
    prediction_path: Path,
) -> dict[str, Any]:
    gold_by_id = index_records(gold_records, gold_path)
    prediction_by_id = index_records(prediction_records, prediction_path)
    gold_ids = sorted(gold_by_id, key=natural_case_key)
    missing_ids = [case_id for case_id in gold_ids if case_id not in prediction_by_id]
    extra_ids = sorted(
        set(prediction_by_id) - set(gold_by_id), key=natural_case_key
    )

    for case_id in gold_ids:
        schema_errors, graph_errors = schema_errors_for_case(
            gold_by_id[case_id], schema
        )
        if schema_errors or graph_errors:
            raise ValueError(
                f"Gold case {case_id} is invalid: "
                f"{(schema_errors + graph_errors)[:5]}"
            )

    accumulators: dict[str, dict[str, Any]] = {
        group: {
            "items_gold": Counter(),
            "items_prediction": Counter(),
            "structure_gold": Counter(),
            "structure_prediction": Counter(),
            "content_gold": Counter(),
            "content_prediction": Counter(),
            "exact_cases": 0,
            "case_f1": [],
        }
        for group in GROUP_ORDER
    }
    overall_items_gold: Counter[str] = Counter()
    overall_items_prediction: Counter[str] = Counter()
    overall_structure_gold: Counter[str] = Counter()
    overall_structure_prediction: Counter[str] = Counter()
    overall_content_gold: Counter[str] = Counter()
    overall_content_prediction: Counter[str] = Counter()
    money_gold: Counter[str] = Counter()
    money_prediction: Counter[str] = Counter()

    valid_schema_cases = 0
    valid_graph_cases = 0
    exact_cases = 0
    life_status_gold = 0
    life_status_matched = 0
    life_status_correct = 0
    case_reports: list[dict[str, Any]] = []

    for case_id in gold_ids:
        gold_case = gold_by_id[case_id]
        prediction_case = prediction_by_id.get(case_id)
        schema_errors, graph_errors = schema_errors_for_case(
            prediction_case, schema
        )
        schema_valid = not schema_errors
        graph_valid = not graph_errors
        valid_schema_cases += int(schema_valid)
        valid_graph_cases += int(graph_valid)
        metric_prediction_case = prediction_case or {}

        case_structure_gold: Counter[str] = Counter()
        case_structure_prediction: Counter[str] = Counter()
        case_content_gold: Counter[str] = Counter()
        case_content_prediction: Counter[str] = Counter()
        case_group_metrics: dict[str, Any] = {}

        for group in GROUP_ORDER:
            gold_group_records = group_records(gold_case, group)
            prediction_group_records = group_records(
                metric_prediction_case, group
            )
            gold_items = record_item_counter(gold_group_records)
            prediction_items = record_item_counter(prediction_group_records)
            gold_structure = record_fact_counter(
                gold_group_records, content_only=False
            )
            prediction_structure = record_fact_counter(
                prediction_group_records, content_only=False
            )
            gold_content = record_fact_counter(
                gold_group_records, content_only=True
            )
            prediction_content = record_fact_counter(
                prediction_group_records, content_only=True
            )

            accumulator = accumulators[group]
            accumulator["items_gold"].update(gold_items)
            accumulator["items_prediction"].update(prediction_items)
            accumulator["structure_gold"].update(gold_structure)
            accumulator["structure_prediction"].update(prediction_structure)
            accumulator["content_gold"].update(gold_content)
            accumulator["content_prediction"].update(prediction_content)
            is_exact = (
                gold_structure == prediction_structure
                and gold_items == prediction_items
            )
            accumulator["exact_cases"] += int(is_exact)
            case_item_metrics = counter_metrics(
                gold_items, prediction_items, empty_is_perfect=True
            )
            accumulator["case_f1"].append(case_item_metrics["f1"])

            merge_counter(overall_items_gold, gold_items, group)
            merge_counter(overall_items_prediction, prediction_items, group)
            merge_counter(overall_structure_gold, gold_structure, group)
            merge_counter(
                overall_structure_prediction, prediction_structure, group
            )
            merge_counter(overall_content_gold, gold_content, group)
            merge_counter(overall_content_prediction, prediction_content, group)
            merge_counter(case_structure_gold, gold_structure, group)
            merge_counter(
                case_structure_prediction, prediction_structure, group
            )
            merge_counter(case_content_gold, gold_content, group)
            merge_counter(case_content_prediction, prediction_content, group)

            case_group_metrics[group] = {
                "item_f1": case_item_metrics["f1"],
                "exact": is_exact,
            }

        money_gold.update(monetary_counter(gold_case))
        money_prediction.update(monetary_counter(metric_prediction_case))

        gold_life_status = life_status_pairs(gold_case)
        prediction_life_status = life_status_pairs(metric_prediction_case)
        life_status_gold += len(gold_life_status)
        for name, gold_status in gold_life_status.items():
            if name in prediction_life_status:
                life_status_matched += 1
                life_status_correct += int(
                    prediction_life_status[name] == gold_status
                )

        case_exact = (
            schema_valid
            and graph_valid
            and normalize_string(
                str(metric_prediction_case.get("schema_version", ""))
            )
            == normalize_string(str(gold_case.get("schema_version", "")))
            and case_structure_gold == case_structure_prediction
        )
        exact_cases += int(case_exact)
        case_content_metrics = counter_metrics(
            case_content_gold,
            case_content_prediction,
            empty_is_perfect=True,
        )
        case_reports.append(
            {
                "case_id": case_id,
                "missing_prediction": prediction_case is None,
                "schema_valid": schema_valid,
                "graph_valid": graph_valid,
                "schema_error_count": len(schema_errors),
                "graph_error_count": len(graph_errors),
                "error_examples": (schema_errors + graph_errors)[:10],
                "case_exact_match": case_exact,
                "content_f1": case_content_metrics["f1"],
                "groups": case_group_metrics,
            }
        )

    group_results: dict[str, Any] = {}
    supported_group_f1: list[float] = []
    for group in GROUP_ORDER:
        accumulator = accumulators[group]
        item_metrics = counter_metrics(
            accumulator["items_gold"], accumulator["items_prediction"]
        )
        structure_metrics = counter_metrics(
            accumulator["structure_gold"],
            accumulator["structure_prediction"],
        )
        content_metrics = counter_metrics(
            accumulator["content_gold"],
            accumulator["content_prediction"],
        )
        if item_metrics["f1"] is not None:
            supported_group_f1.append(float(item_metrics["f1"]))
        group_results[group] = {
            "label": GROUP_LABELS[group],
            "items": item_metrics,
            "structure": structure_metrics,
            "content": content_metrics,
            "exact_cases": accumulator["exact_cases"],
            "exact_case_rate": accumulator["exact_cases"] / len(gold_ids),
            "macro_case_f1": sum(accumulator["case_f1"])
            / len(accumulator["case_f1"]),
        }

    money_metrics = counter_metrics(money_gold, money_prediction)
    money_accuracy = (
        money_metrics["true_positive"] / money_metrics["gold"]
        if money_metrics["gold"]
        else None
    )
    life_status_accuracy = (
        life_status_correct / life_status_gold if life_status_gold else None
    )

    case_reports.sort(
        key=lambda row: (
            float(row["content_f1"])
            if row["content_f1"] is not None
            else math.inf,
            natural_case_key(row["case_id"]),
        )
    )
    return {
        "protocol": {
            "name": "IGEP full-schema extraction evaluation",
            "schema_version": "2.2.0",
            "case_policy": "all_gold_cases",
            "repair_log_filtering": False,
            "group_metrics": True,
            "structure_includes_placeholders": True,
            "content_excludes": [None, "", "unknown", "not_mentioned", [], {}],
            "symmetric_relations": sorted(SYMMETRIC_RELATIONS),
            "technical_ids_scored": False,
            "array_order_scored": False,
        },
        "inputs": {
            "gold_path": str(gold_path.resolve()),
            "prediction_path": str(prediction_path.resolve()),
            "gold_sha256": sha256(gold_path),
            "prediction_sha256": sha256(prediction_path),
        },
        "coverage": {
            "gold_cases": len(gold_ids),
            "prediction_records": len(prediction_by_id),
            "evaluated_cases": len(gold_ids),
            "missing_prediction_cases": missing_ids,
            "extra_prediction_cases": extra_ids,
        },
        "validation": {
            "schema_valid_cases": valid_schema_cases,
            "schema_valid_rate": valid_schema_cases / len(gold_ids),
            "graph_valid_cases": valid_graph_cases,
            "graph_valid_rate": valid_graph_cases / len(gold_ids),
        },
        "overall": {
            "primary_items_micro": counter_metrics(
                overall_items_gold, overall_items_prediction
            ),
            "structure_micro": counter_metrics(
                overall_structure_gold, overall_structure_prediction
            ),
            "content_micro": counter_metrics(
                overall_content_gold, overall_content_prediction
            ),
            "macro_group_f1": (
                sum(supported_group_f1) / len(supported_group_f1)
                if supported_group_f1
                else None
            ),
            "case_exact_matches": exact_cases,
            "case_exact_match_rate": exact_cases / len(gold_ids),
        },
        "derived_metrics": {
            "monetary_value_exact": {
                **money_metrics,
                "accuracy": money_accuracy,
            },
            "life_status": {
                "gold_persons": life_status_gold,
                "matched_persons": life_status_matched,
                "correct": life_status_correct,
                "accuracy": life_status_accuracy,
            },
        },
        "groups": group_results,
        "cases": case_reports,
    }


def format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    validation = report["validation"]
    overall = report["overall"]
    money = report["derived_metrics"]["monetary_value_exact"]
    life = report["derived_metrics"]["life_status"]
    lines = [
        "# Full-schema extraction evaluation",
        "",
        "## Protocol",
        "",
        "- Gold schema: v2.2.0.",
        f"- Evaluated cases: {coverage['evaluated_cases']}/"
        f"{coverage['gold_cases']}.",
        "- Không lọc case bằng repair log.",
        "- Metric được báo riêng theo từng nhóm schema.",
        "- `structure` tính cả `null`, `unknown`, `not_mentioned` và container rỗng.",
        "- `content` loại các placeholder trên để tránh điểm cao do dự đoán rỗng.",
        "- Technical IDs và thứ tự phần tử trong array không được chấm.",
        "",
        "## Coverage and validation",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Gold cases | {coverage['gold_cases']} |",
        f"| Prediction records | {coverage['prediction_records']} |",
        f"| Missing prediction cases | "
        f"{len(coverage['missing_prediction_cases'])} |",
        f"| Extra prediction cases | "
        f"{len(coverage['extra_prediction_cases'])} |",
        f"| Schema-valid rate | "
        f"{format_metric(validation['schema_valid_rate'])} |",
        f"| Graph-valid rate | "
        f"{format_metric(validation['graph_valid_rate'])} |",
        f"| Case exact-match rate | "
        f"{format_metric(overall['case_exact_match_rate'])} |",
        "",
        "## Metrics by schema group",
        "",
        "| Group | Gold items | Predicted | Precision | Recall | F1 | "
        "Structure F1 | Content F1 | Exact-case rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in GROUP_ORDER:
        result = report["groups"][group]
        items = result["items"]
        lines.append(
            f"| {result['label']} | {items['gold']} | {items['predicted']} | "
            f"{format_metric(items['precision'])} | "
            f"{format_metric(items['recall'])} | "
            f"{format_metric(items['f1'])} | "
            f"{format_metric(result['structure']['f1'])} | "
            f"{format_metric(result['content']['f1'])} | "
            f"{format_metric(result['exact_case_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Overall and derived metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Primary-item micro F1 | "
            f"{format_metric(overall['primary_items_micro']['f1'])} |",
            f"| Structure micro F1 | "
            f"{format_metric(overall['structure_micro']['f1'])} |",
            f"| Content micro F1 | "
            f"{format_metric(overall['content_micro']['f1'])} |",
            f"| Macro group F1 | "
            f"{format_metric(overall['macro_group_f1'])} |",
            f"| Monetary exact accuracy | "
            f"{format_metric(money['accuracy'])} |",
            f"| Life-status accuracy | "
            f"{format_metric(life['accuracy'])} |",
            "",
            "## Lowest-content cases",
            "",
            "| Case | Content F1 | Schema valid | Graph valid | Exact |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for case in report["cases"][:20]:
        lines.append(
            f"| {case['case_id']} | {format_metric(case['content_f1'])} | "
            f"{case['schema_valid']} | {case['graph_valid']} | "
            f"{case['case_exact_match']} |"
        )
    if coverage["missing_prediction_cases"]:
        lines.extend(
            [
                "",
                "Missing prediction cases: "
                + ", ".join(coverage["missing_prediction_cases"]),
            ]
        )
    if coverage["extra_prediction_cases"]:
        lines.extend(
            [
                "",
                "Extra prediction cases: "
                + ", ".join(coverage["extra_prediction_cases"]),
            ]
        )
    lines.extend(
        [
            "",
            "Kết quả trong report này luôn dùng toàn bộ gold cases; repair log chỉ "
            "phục vụ truy vết và không thay đổi mẫu số.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate full-schema v2.2 extractor predictions."
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help="Prediction JSON array or JSONL file.",
    )
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--split", choices=["development", "test"], default="development"
    )
    parser.add_argument(
        "--split-manifest", type=Path, default=DEFAULT_SPLIT_MANIFEST
    )
    parser.add_argument("--allow-held-out-test", action="store_true")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_path = args.gold.resolve()
    prediction_path = args.predictions.resolve()
    schema_path = args.schema.resolve()
    if not gold_path.exists():
        raise FileNotFoundError(gold_path)
    if not prediction_path.exists():
        raise FileNotFoundError(prediction_path)
    if not schema_path.exists():
        raise FileNotFoundError(schema_path)
    if args.split == "test" and not args.allow_held_out_test:
        raise ValueError(
            "Held-out test evaluation is locked. Freeze the complete method first, "
            "then pass --allow-held-out-test explicitly."
        )

    with args.split_manifest.open(encoding="utf-8-sig", newline="") as handle:
        allowed = {
            str(row["case_id"])
            for row in csv.DictReader(handle)
            if row["split"] == args.split
        }
    gold_records = [
        row for row in load_records(gold_path) if str(row.get("case_id")) in allowed
    ]
    prediction_records = [
        row
        for row in load_records(prediction_path)
        if str(row.get("case_id")) in allowed
    ]

    schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
    report = evaluate(
        gold_records,
        prediction_records,
        schema,
        gold_path=gold_path,
        prediction_path=prediction_path,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output_md.write_text(
        render_markdown(report),
        encoding="utf-8",
    )

    print(
        f"Evaluated {report['coverage']['evaluated_cases']} full-schema cases."
    )
    print(
        "Schema-valid rate: "
        f"{report['validation']['schema_valid_rate']:.4f}"
    )
    print(
        "Content micro F1: "
        f"{report['overall']['content_micro']['f1']:.4f}"
    )
    print(
        "Case exact-match rate: "
        f"{report['overall']['case_exact_match_rate']:.4f}"
    )
    print(f"JSON report: {args.output_json.resolve()}")
    print(f"Markdown report: {args.output_md.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
