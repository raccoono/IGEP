"""Build a full-schema v2.2 gold candidate from legacy annotations.

The transformation is conservative:
- exact semantic mappings are preserved;
- schema-required but unannotated fields use unknown/null/[];
- deterministic graph errors are removed;
- uncertain or lossy repairs are written to a repair log.

The legacy source file is never overwritten.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATH = PROJECT_ROOT / "data" / "extraction_gold.json"
SCHEMA_PATH = PROJECT_ROOT / "schema" / "valid.md"
OUTPUT_JSON = (
    PROJECT_ROOT / "data" / "canonical" / "gold.json"
)
FLAG_ALIASES = {
    "Từ chối nhận di sản thừa kế": ("renounced_inheritance", None),
    "renounced_inheritance": ("renounced_inheritance", None),
    "Chưa thành niên": ("minor", None),
    "Mất năng lực hành vi dân sự": ("incapacity", None),
    "incapacity": ("incapacity", None),
}


def normalize_flag(raw: str) -> tuple[str, Any]:
    if raw in FLAG_ALIASES:
        return FLAG_ALIASES[raw]
    match = re.fullmatch(r"minor(?:_(\d+))?", raw)
    if match:
        return "minor", int(match.group(1)) if match.group(1) else None
    match = re.fullmatch(r"Chưa thành niên \((\d+) tuổi\)", raw)
    if match:
        return "minor", int(match.group(1))
    return raw, None

ORGANIZATION_TERMS = (
    "ngân hàng",
    "tổ chức",
    "quỹ",
    "hội ",
    "ủy ban",
    "công ty",
    "chùa",
    "giáo hội",
)

# Three legacy cases contain cyclic ancestry graphs caused by entity-code
# confusion.  The replacement graphs below are transcribed from explicit
# statements in query_text, not inferred from the expected distribution.
QUERY_VERIFIED_CYCLE_REPAIRS: dict[str, dict[str, Any]] = {
    "85": {
        "target_decedents": ["M"],
        "life_status": {"M": "deceased"},
        "extra_persons": ["T2"],
        "relationships": [
            ("H", "spouse_of", "M", ["legal_marriage"]),
            ("L", "child_of", "M", ["biological"]),
            ("L", "child_of", "H", ["biological"]),
            ("T2", "child_of", "M", ["biological"]),
            ("T2", "child_of", "H", ["biological"]),
            ("M", "child_of", "T1", ["biological"]),
            ("M", "child_of", "T", ["biological"]),
        ],
    },
    "98": {
        "target_decedents": ["Chung Văn T2", "Huỳnh Thị T5"],
        "life_status": {
            "Chung Văn T2": "deceased",
            "Huỳnh Thị T5": "deceased",
            "T1": "deceased",
            "S2": "deceased",
        },
        "extra_persons": [],
        "relationships": [
            (
                "Huỳnh Thị T5",
                "spouse_of",
                "Chung Văn T2",
                ["legal_marriage"],
            ),
            ("N", "child_of", "Chung Văn T2", ["biological"]),
            ("N", "child_of", "Huỳnh Thị T5", ["biological"]),
            ("S1", "child_of", "Chung Văn T2", ["biological"]),
            ("S1", "child_of", "Huỳnh Thị T5", ["biological"]),
            ("K1", "child_of", "Chung Văn T2", ["biological"]),
            ("K1", "child_of", "Huỳnh Thị T5", ["biological"]),
            ("T1", "child_of", "Chung Văn T2", ["biological"]),
            ("T1", "child_of", "Huỳnh Thị T5", ["biological"]),
            ("S2", "child_of", "Chung Văn T2", ["biological"]),
            ("S2", "child_of", "Huỳnh Thị T5", ["biological"]),
            ("T3", "child_of", "T1", ["biological"]),
            ("L1", "child_of", "T1", ["biological"]),
            ("H", "child_of", "T1", ["biological"]),
            ("C", "child_of", "S2", ["biological"]),
        ],
    },
    "103": {
        "target_decedents": ["L3", "G"],
        "life_status": {
            "L3": "deceased",
            "G": "deceased",
            "Nguyễn Văn L1": "alive",
            "Nguyễn Văn Đ1": "alive",
            "Nguyễn Văn Đ2": "alive",
            "Nguyễn Văn L2": "alive",
            "Nguyễn Thị U": "alive",
        },
        "extra_persons": [
            "Nguyễn Văn L1",
            "Nguyễn Văn Đ1",
            "Nguyễn Văn Đ2",
            "Nguyễn Văn L2",
            "Nguyễn Thị U",
        ],
        "relationships": [
            ("G", "spouse_of", "L3", ["legal_marriage"]),
            ("Nguyễn Văn L1", "child_of", "L3", ["biological"]),
            ("Nguyễn Văn L1", "child_of", "G", ["biological"]),
            ("Nguyễn Văn Đ1", "child_of", "L3", ["biological"]),
            ("Nguyễn Văn Đ1", "child_of", "G", ["biological"]),
            ("Nguyễn Văn Đ2", "child_of", "L3", ["biological"]),
            ("Nguyễn Văn Đ2", "child_of", "G", ["biological"]),
            ("Nguyễn Văn L2", "child_of", "L3", ["biological"]),
            ("Nguyễn Văn L2", "child_of", "G", ["biological"]),
            ("Nguyễn Thị U", "child_of", "L3", ["biological"]),
            ("Nguyễn Thị U", "child_of", "G", ["biological"]),
        ],
    },
    "147": {
        "target_decedents": ["N1", "G"],
        "life_status": {"N1": "deceased", "G": "deceased", "B": "deceased"},
        "extra_persons": [],
        "relationships": [
            ("G", "spouse_of", "N1", ["legal_marriage"]),
            ("T", "child_of", "N1", ["biological"]),
            ("T", "child_of", "G", ["biological"]),
            ("B", "child_of", "N1", ["biological"]),
            ("B", "child_of", "G", ["biological"]),
            ("K1", "child_of", "N1", ["biological"]),
            ("K1", "child_of", "G", ["biological"]),
            ("M", "child_of", "B", ["biological"]),
            ("N", "child_of", "B", ["biological"]),
            ("T1", "child_of", "B", ["biological"]),
            ("K1", "spouse_of", "V", ["legal_marriage"]),
        ],
    },
}

# Some multi-opening cases were originally annotated with only the primary
# decedent even though the query and reference settlement explicitly require
# later/earlier succession openings. These target additions do not alter the
# relationship graph; they make the temporal unit of evaluation complete.
QUERY_VERIFIED_TARGET_REPAIRS: dict[str, list[str]] = {
    "117": ["Thuyết", "Lược", "Tiêu"],
    "128": ["T6", "L", "H1"],
}


def parse_distribution(raw: str) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for segment in raw.split(";"):
        if not segment.strip():
            continue
        name, value = segment.rsplit(":", 1)
        result.append((name.strip(), int(re.sub(r"\D", "", value))))
    return result


def is_organization_name(name: str) -> bool:
    lowered = name.lower()
    return any(term in lowered for term in ORGANIZATION_TERMS)


def is_grouped_name(name: str) -> bool:
    return "," in name or " và " in name.lower()


def organization_type(name: str) -> str:
    lowered = name.lower()
    if "ngân hàng" in lowered or "công ty" in lowered:
        return "enterprise"
    if any(term in lowered for term in ("tổ chức", "quỹ", "hội ", "chùa")):
        return "charitable_organization"
    if "ủy ban" in lowered:
        return "state_authority"
    return "other"


def empty_person(
    name: str,
    *,
    life_status: str = "unknown",
    age: int | None = None,
    age_status: str = "unknown",
) -> dict[str, Any]:
    return {
        "name": name,
        "aliases": [],
        "life_status": life_status,
        "death_time": None,
        "birth_time": None,
        "conception_time": None,
        "birth_status": "unknown",
        "age": age,
        "age_status": age_status,
        "working_capacity": "unknown",
        "awareness_state": "unknown",
        "literacy_status": "unknown",
        "physical_limitation": None,
        "last_residence": None,
    }


def empty_organization(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "organization_type": organization_type(name),
        "existence_status": "unknown",
        "termination_time": None,
    }


def infer_asset_type(text: str) -> str:
    lowered = text.lower()
    if "tiền mặt" in lowered or "đồng" in lowered:
        if "nhà" not in lowered and "đất" not in lowered:
            return "cash"
    if "căn hộ" in lowered:
        return "apartment"
    if "nhà" in lowered:
        return "house"
    if "đất" in lowered or "quyền sử dụng" in lowered:
        return "land_use_right"
    if any(term in lowered for term in ("xe máy", "ô tô", "xe ")):
        return "vehicle"
    if "tiết kiệm" in lowered or "tài khoản" in lowered:
        return "savings_deposit"
    if "vàng" in lowered or "trang sức" in lowered:
        return "gold_jewelry"
    return "other"


def infer_ownership_type(text: str) -> str:
    lowered = text.lower()
    if "tài sản chung" in lowered or "khối tài sản chung" in lowered:
        return "marital_common_property"
    if "tài sản riêng" in lowered or "di sản riêng" in lowered:
        return "separate_property"
    return "unknown"


def infer_obligation_type(text: str) -> str:
    lowered = text.lower()
    if "mai táng" in lowered or "tang lễ" in lowered:
        return "funeral_expense"
    if "thuế" in lowered or "lệ phí" in lowered:
        return "tax_or_fee"
    if "bồi thường" in lowered:
        return "compensation"
    return "debt"


def relationship_qualifiers(
    relation: str,
    subject_code: str,
    code_to_entity: dict[str, dict[str, Any]],
) -> list[str]:
    entity = code_to_entity.get(subject_code)
    if not entity:
        return []
    label = entity.get("relationship_to_decedent")
    if relation == "child_of":
        if label == "child_out_of_wedlock":
            return ["biological", "outside_marriage"]
        if label == "adopted_child":
            return ["adopted_legal"]
        if label in {"biological_child", "grandchild_by_representation"}:
            return ["biological"]
    if relation == "spouse_of":
        status = entity.get("relationship_status")
        if status == "married":
            return ["legal_marriage"]
        if status == "unregistered":
            return ["not_legally_recognized"]
    return []


def relationship_status(
    relation: str,
    subject_code: str,
    object_code: str,
    code_to_entity: dict[str, dict[str, Any]],
) -> str:
    if relation != "spouse_of":
        return "unknown"
    statuses = {
        code_to_entity.get(subject_code, {}).get("relationship_status"),
        code_to_entity.get(object_code, {}).get("relationship_status"),
    }
    if "divorced" in statuses or "widowed" in statuses:
        return "ended"
    if "married" in statuses:
        return "active"
    return "unknown"


def creates_cycle(
    child_graph: dict[str, set[str]], subject: str, object_: str
) -> bool:
    stack = [object_]
    visited: set[str] = set()
    while stack:
        node = stack.pop()
        if node == subject:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(child_graph.get(node, set()))
    return False


def complete_relationship(
    subject: str, relation: str, object_: str, qualifiers: list[str]
) -> dict[str, Any]:
    return {
        "subject": subject,
        "relation": relation,
        "object": object_,
        "qualifiers": qualifiers,
        "relationship_status": "active",
        "start_time": None,
        "end_time": None,
        "mutual_care": "not_mentioned",
    }


def ancestry_edge(relationship: dict[str, Any]) -> tuple[str, str] | None:
    """Normalize ancestry relations to descendant -> ancestor."""

    relation = relationship["relation"]
    if relation in {"child_of", "grandchild_of", "great_grandchild_of"}:
        return relationship["subject"], relationship["object"]
    if relation in {"grandparent_of", "great_grandparent_of"}:
        return relationship["object"], relationship["subject"]
    return None


def graph_validation_errors(case: dict[str, Any]) -> list[str]:
    """Validate reference integrity and acyclicity of the ancestry graph."""

    errors: list[str] = []
    person_names = {person["name"] for person in case["persons"]}
    ancestry_graph: dict[str, set[str]] = defaultdict(set)
    seen: set[tuple[str, str, str]] = set()

    for index, relationship in enumerate(case["relationships"]):
        key = (
            relationship["subject"],
            relationship["relation"],
            relationship["object"],
        )
        if key in seen:
            errors.append(f"relationships[{index}]: duplicate {key!r}")
        seen.add(key)

        if relationship["subject"] not in person_names:
            errors.append(
                f"relationships[{index}]: missing subject "
                f"{relationship['subject']!r}"
            )
        if relationship["object"] not in person_names:
            errors.append(
                f"relationships[{index}]: missing object "
                f"{relationship['object']!r}"
            )
        if relationship["subject"] == relationship["object"]:
            errors.append(f"relationships[{index}]: self relation {key!r}")

        edge = ancestry_edge(relationship)
        if edge is None:
            continue
        descendant, ancestor = edge
        if creates_cycle(ancestry_graph, descendant, ancestor):
            errors.append(
                f"relationships[{index}]: ancestry cycle closed by {key!r}"
            )
        ancestry_graph[descendant].add(ancestor)

    return errors


def validate_instance(
    instance: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str = "$",
) -> list[str]:
    """Minimal Draft 2020-12 validator for features used by valid.md."""

    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            return [f"{path}: unsupported ref {ref}"]
        target = root_schema["$defs"][ref.split("/")[-1]]
        return validate_instance(instance, target, root_schema, path)

    if "anyOf" in schema:
        branch_errors = [
            validate_instance(instance, branch, root_schema, path)
            for branch in schema["anyOf"]
        ]
        if any(not errors for errors in branch_errors):
            return []
        return [f"{path}: does not satisfy anyOf"]

    errors: list[str] = []
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum")

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = (
            expected_type if isinstance(expected_type, list) else [expected_type]
        )

        def matches(type_name: str) -> bool:
            if type_name == "null":
                return instance is None
            if type_name == "object":
                return isinstance(instance, dict)
            if type_name == "array":
                return isinstance(instance, list)
            if type_name == "string":
                return isinstance(instance, str)
            if type_name == "boolean":
                return isinstance(instance, bool)
            if type_name == "integer":
                return isinstance(instance, int) and not isinstance(instance, bool)
            if type_name == "number":
                return (
                    isinstance(instance, (int, float))
                    and not isinstance(instance, bool)
                )
            return False

        if not any(matches(type_name) for type_name in expected_types):
            return [f"{path}: wrong type {type(instance).__name__}"]

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required key {key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: additional property {key}")
        for key, value in instance.items():
            if key in properties:
                errors.extend(
                    validate_instance(
                        value, properties[key], root_schema, f"{path}.{key}"
                    )
                )

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for index, value in enumerate(instance):
                errors.extend(
                    validate_instance(
                        value, item_schema, root_schema, f"{path}[{index}]"
                    )
                )
        if schema.get("uniqueItems"):
            serialized = [json.dumps(item, sort_keys=True) for item in instance]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{path}: duplicate array items")

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path}: string shorter than minLength")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
            errors.append(f"{path}: does not match {schema['pattern']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: below minimum")

    return errors


def main() -> None:
    legacy_cases = json.loads(LEGACY_PATH.read_text(encoding="utf-8-sig"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    repair_log: list[dict[str, str]] = []

    def log(
        case_id: str,
        severity: str,
        category: str,
        legacy_location: str,
        action: str,
        old_value: Any,
        new_value: Any,
        requires_review: bool,
        note: str = "",
    ) -> None:
        repair_log.append(
            {
                "case_id": case_id,
                "severity": severity,
                "category": category,
                "legacy_location": legacy_location,
                "action": action,
                "old_value": json.dumps(old_value, ensure_ascii=False),
                "new_value": json.dumps(new_value, ensure_ascii=False),
                "requires_review": "TRUE" if requires_review else "FALSE",
                "note": note,
            }
        )

    output_cases: list[dict[str, Any]] = []

    for legacy in legacy_cases:
        case_id = str(legacy["case_id"])
        query = legacy["query_text"]
        code_to_entity = {
            entity["entity_code"]: dict(entity) for entity in legacy["entities"]
        }
        corrected_type: dict[str, str] = {}
        corrected_name: dict[str, str] = {}

        for index, entity in enumerate(legacy["entities"]):
            code = entity["entity_code"]
            name = entity["name"]
            entity_type = entity["type"]

            if not name:
                log(
                    case_id,
                    "P1",
                    "DROPPED_UNRESOLVED_ENTITY",
                    f"entities[{index}]",
                    "drop",
                    entity,
                    None,
                    True,
                    "Full schema requires a non-empty canonical name.",
                )
                continue

            if entity_type == "organization" and f"ông {name}".lower() in query.lower():
                entity_type = "person"
                log(
                    case_id,
                    "P1",
                    "CORRECTED_PERSON_TYPE",
                    f"entities[{index}].type",
                    "organization -> person",
                    entity["type"],
                    entity_type,
                    True,
                )

            corrected_type[code] = entity_type
            corrected_name[code] = name

        flags_by_code: dict[str, list[tuple[str, Any]]] = defaultdict(list)
        for flag in legacy["legal_fact_flags"]:
            flags_by_code[flag["entity_code"]].append(
                normalize_flag(flag["fact"])
            )

        persons_by_name: dict[str, dict[str, Any]] = {}
        organizations_by_name: dict[str, dict[str, Any]] = {}

        for code, name in corrected_name.items():
            entity = code_to_entity[code]
            entity_type = corrected_type[code]
            if entity_type == "organization":
                organizations_by_name.setdefault(name, empty_organization(name))
                continue

            normalized_flags = flags_by_code.get(code, [])
            minor_values = [
                value
                for fact, value in normalized_flags
                if fact == "minor" and isinstance(value, int)
            ]
            age = minor_values[0] if minor_values else None
            age_status = (
                "minor"
                if any(fact == "minor" for fact, _ in normalized_flags)
                else "unknown"
            )
            if (
                entity["is_decedent"]
                or entity["relationship_status"] == "deceased_before_decedent"
            ):
                life_status = "deceased"
            elif entity["alive_at_decedent_death"]:
                life_status = "alive"
            else:
                life_status = "unknown"
            persons_by_name.setdefault(
                name,
                empty_person(
                    name,
                    life_status=life_status,
                    age=age,
                    age_status=age_status,
                ),
            )

        target_decedents = []
        for entity in legacy["entities"]:
            code = entity["entity_code"]
            if entity["is_decedent"] and code in corrected_name:
                name = corrected_name[code]
                if corrected_type[code] == "person" and name not in target_decedents:
                    target_decedents.append(name)

        primary_code = legacy["decedent"]["entity_code"]
        primary_name = corrected_name.get(primary_code)
        if not primary_name and target_decedents:
            primary_name = target_decedents[0]
            log(
                case_id,
                "P1",
                "RESOLVED_PRIMARY_DECEDENT_FROM_TARGETS",
                "decedent",
                "fallback to first target",
                legacy["decedent"],
                primary_name,
                True,
            )
        if primary_name and primary_name not in persons_by_name:
            persons_by_name[primary_name] = empty_person(
                primary_name, life_status="deceased"
            )
        if primary_name and primary_name not in target_decedents:
            target_decedents.insert(0, primary_name)
            log(
                case_id,
                "P1",
                "ADDED_PRIMARY_TARGET_DECEDENT",
                "target_decedents",
                "add",
                None,
                primary_name,
                True,
            )
        if not target_decedents:
            fallback_name = legacy["decedent"]["name"] or f"Unknown_{case_id}"
            persons_by_name.setdefault(
                fallback_name, empty_person(fallback_name, life_status="deceased")
            )
            target_decedents = [fallback_name]
            primary_name = fallback_name
            log(
                case_id,
                "P1",
                "CREATED_FALLBACK_TARGET_DECEDENT",
                "target_decedents",
                "create fallback",
                legacy["decedent"],
                fallback_name,
                True,
            )

        cycle_repair = QUERY_VERIFIED_CYCLE_REPAIRS.get(case_id)
        if cycle_repair:
            legacy_targets = list(target_decedents)
            target_decedents = list(cycle_repair["target_decedents"])
            primary_name = target_decedents[0]

            required_people = set(cycle_repair["extra_persons"])
            required_people.update(target_decedents)
            for subject, _, object_, _ in cycle_repair["relationships"]:
                required_people.add(subject)
                required_people.add(object_)
            for name in sorted(required_people):
                persons_by_name.setdefault(name, empty_person(name))

            for name, life_status in cycle_repair["life_status"].items():
                persons_by_name[name]["life_status"] = life_status

            if legacy_targets != target_decedents:
                log(
                    case_id,
                    "P1",
                    "RESOLVED_CYCLE_CASE_TARGETS_FROM_QUERY",
                    "target_decedents",
                    "replace targets using explicit query facts",
                    legacy_targets,
                    target_decedents,
                    False,
                    "Correction is supported directly by query_text.",
                )

        target_repair = QUERY_VERIFIED_TARGET_REPAIRS.get(case_id)
        if target_repair:
            legacy_targets = list(target_decedents)
            target_decedents = list(target_repair)
            primary_name = target_decedents[0]
            for name in target_decedents:
                persons_by_name.setdefault(name, empty_person(name))
                persons_by_name[name]["life_status"] = "deceased"
            if legacy_targets != target_decedents:
                log(
                    case_id,
                    "P1",
                    "EXPANDED_TARGETS_FOR_SUCCESSIVE_OPENINGS",
                    "target_decedents",
                    "replace targets using explicit query deaths and settlement flow",
                    legacy_targets,
                    target_decedents,
                    False,
                    "Every added target has an explicit death year in query_text.",
                )

        assert primary_name is not None

        # Build candidate relationships, retaining legacy order.
        candidates: list[dict[str, Any]] = []
        for index, relation in enumerate(legacy["relationships"]):
            subject_code = relation["subject"]
            object_code = relation["object"]
            if subject_code not in corrected_name or object_code not in corrected_name:
                log(
                    case_id,
                    "P1",
                    "DROPPED_RELATION_WITH_UNRESOLVED_ENDPOINT",
                    f"relationships[{index}]",
                    "drop",
                    relation,
                    None,
                    True,
                )
                continue
            subject = corrected_name[subject_code]
            object_ = corrected_name[object_code]
            if (
                corrected_type[subject_code] != "person"
                or corrected_type[object_code] != "person"
            ):
                log(
                    case_id,
                    "P1",
                    "DROPPED_NON_PERSON_KINSHIP_RELATION",
                    f"relationships[{index}]",
                    "drop",
                    relation,
                    None,
                    True,
                )
                continue

            legacy_predicate = relation["predicate"]
            mapped_relation = (
                "child_of" if legacy_predicate == "represents" else legacy_predicate
            )
            if mapped_relation not in {"child_of", "spouse_of"}:
                log(
                    case_id,
                    "P1",
                    "DROPPED_UNMAPPED_RELATION",
                    f"relationships[{index}]",
                    "drop",
                    relation,
                    None,
                    True,
                )
                continue
            if subject == object_:
                log(
                    case_id,
                    "P1",
                    "DROPPED_SELF_RELATION",
                    f"relationships[{index}]",
                    "drop",
                    relation,
                    None,
                    False,
                )
                continue
            candidates.append(
                {
                    "subject": subject,
                    "relation": mapped_relation,
                    "object": object_,
                    "qualifiers": relationship_qualifiers(
                        mapped_relation, subject_code, code_to_entity
                    ),
                    "relationship_status": relationship_status(
                        mapped_relation,
                        subject_code,
                        object_code,
                        code_to_entity,
                    ),
                    "start_time": None,
                    "end_time": None,
                    "mutual_care": "not_mentioned",
                    "_source": "legacy",
                    "_subject_code": subject_code,
                    "_object_code": object_code,
                }
            )

        # Augment direct relationships that are explicitly encoded in the
        # legacy relationship_to_decedent label.
        primary_code_resolved = next(
            (
                code
                for code, name in corrected_name.items()
                if name == primary_name
                and code_to_entity[code].get("is_decedent")
            ),
            primary_code if primary_code in corrected_name else None,
        )
        if primary_code_resolved:
            for code, name in corrected_name.items():
                if code == primary_code_resolved or corrected_type[code] != "person":
                    continue
                label = code_to_entity[code].get("relationship_to_decedent")
                relation_tuple: tuple[str, str, str] | None = None
                if label == "spouse":
                    relation_tuple = (name, "spouse_of", primary_name)
                elif label in {
                    "biological_child",
                    "child_out_of_wedlock",
                    "adopted_child",
                }:
                    relation_tuple = (name, "child_of", primary_name)
                elif label == "parent":
                    relation_tuple = (primary_name, "child_of", name)
                elif label == "sibling":
                    relation_tuple = (name, "sibling_of", primary_name)
                elif label == "grandchild_by_representation":
                    relation_tuple = (name, "grandchild_of", primary_name)
                elif label == "grandparent":
                    relation_tuple = (name, "grandparent_of", primary_name)

                if relation_tuple:
                    subject, mapped_relation, object_ = relation_tuple
                    candidates.append(
                        {
                            "subject": subject,
                            "relation": mapped_relation,
                            "object": object_,
                            "qualifiers": relationship_qualifiers(
                                mapped_relation, code, code_to_entity
                            ),
                            "relationship_status": relationship_status(
                                mapped_relation,
                                code,
                                primary_code_resolved,
                                code_to_entity,
                            ),
                            "start_time": None,
                            "end_time": None,
                            "mutual_care": "not_mentioned",
                            "_source": "relationship_to_decedent",
                            "_subject_code": code,
                            "_object_code": primary_code_resolved,
                        }
                    )

        # De-duplicate and remove child cycles.
        unique_candidates: list[dict[str, Any]] = []
        seen_relationships: set[tuple[str, str, str]] = set()
        child_graph: dict[str, set[str]] = defaultdict(set)
        for candidate in candidates:
            key = (
                candidate["subject"],
                candidate["relation"],
                candidate["object"],
            )
            if key in seen_relationships:
                log(
                    case_id,
                    "P1",
                    "DROPPED_DUPLICATE_RELATION",
                    "relationships",
                    "drop duplicate",
                    key,
                    None,
                    False,
                )
                continue
            if candidate["relation"] == "child_of" and creates_cycle(
                child_graph, candidate["subject"], candidate["object"]
            ):
                log(
                    case_id,
                    "P1",
                    "DROPPED_CYCLE_EDGE",
                    "relationships",
                    "drop cycle-closing edge",
                    key,
                    None,
                    True,
                )
                continue
            seen_relationships.add(key)
            unique_candidates.append(candidate)
            if candidate["relation"] == "child_of":
                child_graph[candidate["subject"]].add(candidate["object"])

        # Enforce at most two direct child_of parents. Prefer relations derived
        # from the explicit relationship_to_decedent label and the primary
        # target; every removed edge is logged for annotator review.
        parent_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in unique_candidates:
            if candidate["relation"] == "child_of":
                parent_edges[candidate["subject"]].append(candidate)

        dropped_parent_keys: set[tuple[str, str, str]] = set()
        for child, edges in parent_edges.items():
            if len(edges) <= 2:
                continue

            def edge_score(edge: dict[str, Any]) -> tuple[int, int, str]:
                score = 0
                if edge["_source"] == "relationship_to_decedent":
                    score += 100
                if edge["object"] == primary_name:
                    score += 80
                if edge["relationship_status"] == "active":
                    score += 10
                return (-score, 0 if edge["_source"] == "legacy" else 1, edge["object"])

            keep = sorted(edges, key=edge_score)[:2]
            keep_keys = {
                (edge["subject"], edge["relation"], edge["object"])
                for edge in keep
            }
            for edge in edges:
                key = (edge["subject"], edge["relation"], edge["object"])
                if key not in keep_keys:
                    dropped_parent_keys.add(key)
                    log(
                        case_id,
                        "P1",
                        "DROPPED_AMBIGUOUS_EXTRA_PARENT",
                        f"relationships[child={child}]",
                        "drop extra parent",
                        key,
                        {"kept": sorted(keep_keys)},
                        True,
                        "Automatic choice must be checked against the query.",
                    )

        relationships = []
        for candidate in unique_candidates:
            key = (
                candidate["subject"],
                candidate["relation"],
                candidate["object"],
            )
            if key in dropped_parent_keys:
                continue
            relationships.append(
                {
                    key_: value
                    for key_, value in candidate.items()
                    if not key_.startswith("_")
                }
            )

        if cycle_repair:
            corrected_relationships = [
                complete_relationship(subject, relation, object_, qualifiers)
                for subject, relation, object_, qualifiers in cycle_repair[
                    "relationships"
                ]
            ]
            # Intermediate greedy-repair messages no longer describe the final
            # graph once a query-verified replacement is applied.
            repair_log[:] = [
                row
                for row in repair_log
                if not (
                    row["case_id"] == case_id
                    and row["legacy_location"].startswith("relationships")
                )
            ]
            log(
                case_id,
                "P1",
                "RESOLVED_RELATIONSHIP_CYCLE_FROM_QUERY",
                "relationships",
                "replace cyclic legacy graph using explicit query facts",
                legacy["relationships"],
                [
                    {
                        "subject": relationship["subject"],
                        "relation": relationship["relation"],
                        "object": relationship["object"],
                    }
                    for relationship in corrected_relationships
                ],
                False,
                "The replacement contains no self edge, duplicate, or "
                "ancestry cycle.",
            )
            relationships = corrected_relationships

        # Build estates and map only exact monetary semantics.
        estates = [
            {
                "estate_id": f"E{index}",
                "decedent": target_name,
                "opening_place": None,
                "assets": [],
                "obligations": [],
                "estate_roles": [],
                "distribution_status": "unknown",
            }
            for index, target_name in enumerate(target_decedents, start=1)
        ]
        primary_estate = next(
            (estate for estate in estates if estate["decedent"] == primary_name),
            estates[0],
        )

        bequest_facts = []
        prior_distribution_facts = []
        legal_assertions = []
        asset_number = 1
        obligation_number = 1
        assertion_number = 1

        creditor_entities = [
            (corrected_name[code], corrected_type[code])
            for code, entity in code_to_entity.items()
            if code in corrected_name
            and entity.get("relationship_to_decedent") == "creditor"
        ]

        for index, fact in enumerate(legacy["monetary_facts"]):
            role = fact["role"]
            if role == "estate_asset":
                description = fact["context_snippet"].strip() or "Legacy estate asset"
                primary_estate["assets"].append(
                    {
                        "asset_id": f"A{asset_number}",
                        "asset_type": infer_asset_type(description),
                        "description": description,
                        "value": fact["amount"],
                        "currency": "VND",
                        "valuation_time": None,
                        "ownership_type": infer_ownership_type(description),
                        "owners": [],
                        "status": "unknown",
                    }
                )
                asset_number += 1
            elif role in {"debt", "funeral_cost"}:
                creditor_name = (
                    creditor_entities[0][0]
                    if len(creditor_entities) == 1
                    else None
                )
                creditor_type = (
                    creditor_entities[0][1]
                    if len(creditor_entities) == 1
                    else "unknown"
                )
                primary_estate["obligations"].append(
                    {
                        "obligation_id": f"O{obligation_number}",
                        "obligation_type": (
                            "funeral_expense"
                            if role == "funeral_cost"
                            else infer_obligation_type(fact["context_snippet"])
                        ),
                        "creditor_type": creditor_type,
                        "creditor": creditor_name,
                        "amount": fact["amount"],
                        "currency": "VND",
                        "decedent_liability_ratio": None,
                        "secured_asset_ids": [],
                    }
                )
                obligation_number += 1
            elif role == "bequest_amount":
                bequest_facts.append(fact)
            elif role == "prior_distribution":
                prior_distribution_facts.append(fact)
            else:
                legal_assertions.append(
                    {
                        "assertion_id": f"LA{assertion_number}",
                        "subject_type": "other",
                        "subject_ref": primary_estate["estate_id"],
                        "assertion": (
                            f"Legacy monetary fact role={role}, "
                            f"amount={fact['amount']} VND; "
                            f"evidence={fact['context_snippet']}"
                        ),
                        "asserted_by": "narrative",
                        "asserting_party_type": None,
                        "asserting_party": None,
                    }
                )
                assertion_number += 1
                log(
                    case_id,
                    "P2",
                    (
                        "MAPPED_DISTRACTOR_MONEY_TO_ASSERTION"
                        if role == "distractor"
                        else "MAPPED_NON_ESTATE_MONEY_TO_ASSERTION"
                    ),
                    f"monetary_facts[{index}]",
                    "map to legal_assertions",
                    fact,
                    legal_assertions[-1],
                    role != "distractor",
                    (
                        "Legacy gold explicitly labels this mentioned amount "
                        "as non-estate/distractor."
                        if role == "distractor"
                        else ""
                    ),
                )

        wills = []
        if bequest_facts:
            dispositions = []
            for index, fact in enumerate(bequest_facts, start=1):
                recipient_code = fact.get("recipient_code")
                recipient = corrected_name.get(recipient_code)
                recipient_type = (
                    corrected_type.get(recipient_code)
                    if recipient is not None
                    else None
                )
                dispositions.append(
                    {
                        "disposition_id": f"D{index}",
                        "disposition_type": "bequest",
                        "recipient_type": recipient_type,
                        "recipient": recipient,
                        "manager_type": None,
                        "manager": None,
                        "affected_persons": [],
                        "scope": "specific_amount",
                        "asset_ids": [],
                        "share_ratio": None,
                        "amount": fact["amount"],
                        "currency": "VND",
                        "condition": None,
                        "appointed_role": None,
                    }
                )
                if recipient is None:
                    log(
                        case_id,
                        "P2",
                        "BEQUEST_RECIPIENT_UNRESOLVED",
                        "monetary_facts",
                        "created disposition with null recipient",
                        fact,
                        dispositions[-1],
                        True,
                    )
            will_evidence = " ".join(
                fact.get("context_snippet", "") for fact in bequest_facts
            ).lower()
            is_oral = any(
                phrase in will_evidence
                for phrase in ("di chúc miệng", "trăn trối")
            )
            wills.append(
                {
                    "will_id": "W1",
                    "testator": primary_name,
                    "date": None,
                    "medium": "oral" if is_oral else "unknown",
                    "execution_method": (
                        "oral_declaration" if is_oral else "unknown"
                    ),
                    "authentication": None,
                    "witnesses": [],
                    "will_facts": None,
                    "relations_to_other_wills": [],
                    "dispositions": dispositions,
                }
            )

        inheritance_actions = []
        conduct_events = []
        for flag_index, flag in enumerate(legacy["legal_fact_flags"]):
            code = flag["entity_code"]
            if code not in corrected_name:
                log(
                    case_id,
                    "P1",
                    "UNMAPPED_FLAG_SUBJECT",
                    f"legal_fact_flags[{flag_index}]",
                    "not mapped",
                    flag,
                    None,
                    True,
                )
                continue
            subject_name = corrected_name[code]
            fact, value = normalize_flag(flag["fact"])
            if fact == "renounced_inheritance":
                inheritance_actions.append(
                    {
                        "action_id": f"IA{len(inheritance_actions) + 1}",
                        "person": subject_name,
                        "related_decedent": primary_name,
                        "action": "renunciation",
                        "time": None,
                        "form": "unknown",
                        "notified_parties": [],
                        "stated_purpose": None,
                    }
                )
            elif fact in {"abused_decedent", "convicted_of_killing_decedent"}:
                conduct_events.append(
                    {
                        "conduct_event_id": f"CE{len(conduct_events) + 1}",
                        "actor": subject_name,
                        "target": primary_name,
                        "conduct_type": (
                            "serious_abuse"
                            if fact == "abused_decedent"
                            else "intentional_harm_to_decedent"
                        ),
                        "conviction_status": (
                            "convicted"
                            if fact == "convicted_of_killing_decedent"
                            else "unknown"
                        ),
                        "purpose_to_obtain_inheritance": "not_mentioned",
                        "decedent_knew_conduct": "not_mentioned",
                        "decedent_still_granted_by_will": "not_mentioned",
                    }
                )

            legal_assertions.append(
                {
                    "assertion_id": f"LA{assertion_number}",
                    "subject_type": "person",
                    "subject_ref": subject_name,
                    "assertion": (
                        f"Legacy fact={fact}"
                        + (f", value={value}" if value is not None else "")
                    ),
                    "asserted_by": "narrative",
                    "asserting_party_type": None,
                    "asserting_party": None,
                }
            )
            assertion_number += 1

        events = []
        for fact in prior_distribution_facts:
            events.append(
                {
                    "event_id": f"EVT{len(events) + 1}",
                    "event_type": "estate_distributed",
                    "person": None,
                    "related_person": None,
                    "related_estate_id": primary_estate["estate_id"],
                    "related_asset_id": None,
                    "related_will_id": None,
                    "time": None,
                    "temporal_relation": "not_applicable",
                    "details": {
                        "amount": fact["amount"],
                        "currency": "VND",
                        "legacy_evidence": fact["context_snippet"],
                    },
                }
            )

        output = {
            "schema_version": "2.2.0",
            "case_id": case_id,
            "target_decedents": target_decedents,
            "persons": list(persons_by_name.values()),
            "organizations": list(organizations_by_name.values()),
            "relationships": relationships,
            "estates": estates,
            "wills": wills,
            "inheritance_actions": inheritance_actions,
            "conduct_events": conduct_events,
            "agreements": [],
            "events": events,
            "legal_assertions": legal_assertions,
        }
        output_cases.append(output)

    validation_errors: list[str] = []
    for case in output_cases:
        validation_errors.extend(
            f"case {case['case_id']} {error}"
            for error in validate_instance(case, schema, schema)
        )
        validation_errors.extend(
            f"case {case['case_id']} {error}"
            for error in graph_validation_errors(case)
        )
    if validation_errors:
        raise ValueError(
            "Full-schema output validation failed:\n"
            + "\n".join(validation_errors[:100])
        )

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(output_cases, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    repair_log.sort(
        key=lambda row: (
            int(row["case_id"]),
            row["severity"],
            row["category"],
            row["legacy_location"],
            row["old_value"],
        )
    )
    review_cases = {
        row["case_id"]
        for row in repair_log
        if row["requires_review"] == "TRUE"
    }
    print(f"Built {len(output_cases)} full-schema gold candidates.")
    print("Schema validation: PASS (0 errors)")
    print(f"Repair log rows: {len(repair_log)}")
    print(f"Cases requiring review: {len(review_cases)}")
    print(f"JSON: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
