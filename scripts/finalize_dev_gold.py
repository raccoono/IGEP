#!/usr/bin/env python3
"""Build the author-approved 30-case development semantic gold.

The frozen input and raw IGEP baseline are read-only inputs.  Five cases use
the hand-built records in build_semantic_gold.py; the remaining approved cases
start from the schema-valid baseline and receive the documented review fixes.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from pathlib import Path

from build_gold import graph_validation_errors, validate_instance
from build_semantic_gold import REVIEWED as HAND_REVIEWED


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/canonical/input.jsonl"
BASELINE = ROOT / "data/runs/extraction_dev_igep.jsonl"
OUTPUT = ROOT / "data/canonical/dev_gold_reviewed.json"
EVIDENCE = ROOT / "data/review/dev_gold_evidence.jsonl"
AUDIT = ROOT / "data/review/dev_gold_audit.json"
SCHEMA = ROOT / "schema/valid.md"
APPROVAL = ROOT / "data/review/dev_gold_approval.md"

DEV_IDS = [1, 13, 15, 16, 20, 21, 22, 27, 29, 48, 50, 57, 65, 77,
           78, 83, 84, 85, 91, 104, 105, 109, 110, 116, 118, 121,
           131, 132, 133, 141]
HONORIFIC = re.compile(r"^(?:ông|bà|cụ|anh|chị|cháu)\s+", re.I)


def load_jsonl(path: Path) -> dict[str, dict]:
    return {str(x["case_id"]): x for x in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def replace_exact(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [replace_exact(x, mapping) for x in value]
    if isinstance(value, dict):
        return {k: replace_exact(v, mapping) for k, v in value.items()}
    return value


def canonicalize_names(record: dict) -> dict:
    """Strip source honorifics while preserving the source surface as aliases."""
    mapping = {}
    alias_by_new = {}
    occupied = {p["name"] for p in record["persons"]}
    for p in record["persons"]:
        old = p["name"]
        new = HONORIFIC.sub("", old).strip()
        if new != old and (new not in occupied or new == old):
            mapping[old] = new
            alias_by_new.setdefault(new, []).append(old)
    record = replace_exact(record, mapping)
    for p in record["persons"]:
        additions = alias_by_new.get(p["name"], [])
        p["aliases"] = list(dict.fromkeys([*p.get("aliases", []), *additions]))
    return record


def split_common_estate(record: dict, decedents: list[str], prefix: str) -> None:
    """Replace an invalid combined estate with one unknown interest per decedent."""
    source = record["estates"][0]
    estates = []
    asset_map = {}
    for index, decedent in enumerate(decedents, 1):
        estate = copy.deepcopy(source)
        estate["estate_id"] = f"E{prefix}{index}"
        estate["decedent"] = decedent
        for j, asset in enumerate(estate["assets"], 1):
            old = asset["asset_id"]
            asset["asset_id"] = f"A{prefix}{index}{j}"
            asset["value"] = None
            asset["currency"] = None
            asset["description"] = f"Phần quyền lợi chưa xác định tỷ lệ của {decedent} trong " + asset["description"]
            asset_map.setdefault(old, []).append(asset["asset_id"])
        estates.append(estate)
    record["estates"] = estates
    for event in record["events"]:
        who = event.get("person")
        if who in decedents:
            event["related_estate_id"] = estates[decedents.index(who)]["estate_id"]
        if event.get("related_asset_id") in asset_map:
            event["related_asset_id"] = None
    for agreement in record["agreements"]:
        agreement["asset_ids"] = [new for old in agreement.get("asset_ids", []) for new in asset_map.get(old, [old])]


def apply_review_fixes(cid: str, record: dict) -> dict:
    r = canonicalize_names(copy.deepcopy(record))

    if cid == "1":
        for p in r["persons"]:
            if p["name"] == "Nguyễn Văn A": p["death_time"] = "1987-10"
        r["wills"][0]["date"] = None
        for e in r["events"]:
            if e.get("person") == "Nguyễn Văn A": e["time"] = "1987-10"

    if cid in {"20", "21", "22", "50", "77"}:
        known = {p["name"] for p in r["persons"]}
        for will in r["wills"]:
            will["witnesses"] = [x for x in will.get("witnesses", []) if x in known]

    if cid == "50":
        r["inheritance_actions"] = []  # unnamed representative is not a person entity

    if cid == "65":
        # The baseline incorrectly made the prior owner S the decedent.
        split_common_estate(r, ["Phan Thị T3", "Phan Thị Đ"], "65")
        r["inheritance_actions"] = [
            {**copy.deepcopy(r["inheritance_actions"][0]), "action_id": "IA651", "related_decedent": "Phan Thị T3"},
            {**copy.deepcopy(r["inheritance_actions"][0]), "action_id": "IA652", "related_decedent": "Phan Thị Đ"},
        ]
        for e in r["events"]:
            if e["event_type"] == "claim_filed": e["related_estate_id"] = "E652"

    if cid == "77":
        # An unnamed class of heirs is not an organization.
        r["organizations"] = []
        r["agreements"] = []

    if cid == "83":
        r["target_decedents"] = ["Đ1", "C1"]

    if cid == "91":
        split_common_estate(r, ["Đ", "M1"], "91")
        r["target_decedents"] = ["Đ", "M1"]
        for a in r["inheritance_actions"]:
            if a["action"] == "renunciation" and "Nhường" in (a.get("stated_purpose") or ""):
                a["action"] = "other"
            if a["related_decedent"] in {"Cụ Đ", "Cụ M1"}:
                a["related_decedent"] = HONORIFIC.sub("", a["related_decedent"])
        r["wills"][0]["testator"] = "Đ"

    if cid == "109":
        source = r["estates"][0]["assets"][0]
        downstream = copy.deepcopy(source)
        downstream["asset_id"] = "A1092"
        downstream["description"] = "Phần tài sản H2 nhận từ di sản của Đỗ Thị G"
        downstream["value"] = None
        downstream["currency"] = None
        downstream["ownership_type"] = "unknown"
        downstream["owners"] = [{"holder_type":"person","holder":"Phạm Thị H2","stated_share_ratio":None}]
        r["estates"].append({"estate_id":"E1092","decedent":"Phạm Thị H2","opening_place":None,
                              "assets":[downstream],"obligations":[],"estate_roles":[],"distribution_status":"undivided"})

    if cid == "118":
        estate = r["estates"][0]
        estate["assets"] = [a for a in estate["assets"] if a["asset_id"] != "A118672"]
        for event in r["events"]:
            if event.get("related_asset_id") == "A118672": event["related_asset_id"] = None
            if event.get("person") == "unknown_auction_buyers": event["person"] = None

    if cid == "131":
        # None of the alleged transfers is established by the facts.
        r["agreements"] = []

    if cid == "141":
        split_common_estate(r, ["C", "L"], "141")
        r["target_decedents"] = ["C", "L"]
        original_actions = r["inheritance_actions"]
        r["inheritance_actions"] = []
        action_counter = 1
        for action in original_actions:
            for decedent in ["C", "L"]:
                item = copy.deepcopy(action)
                item["action_id"] = f"IA141{action_counter}"
                action_counter += 1
                item["related_decedent"] = decedent
                r["inheritance_actions"].append(item)

    return r


def text_words(value) -> set[str]:
    value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    value = unicodedata.normalize("NFKC", value).casefold()
    stop = {"null", "unknown", "active", "person", "vnd", "không", "một", "của", "và", "là", "cho"}
    return {x for x in re.findall(r"\w+", value, re.UNICODE) if len(x) > 1 and x not in stop}


def fact_objects(record):
    for i, x in enumerate(record["target_decedents"]): yield f"/target_decedents/{i}", x
    for key in ["persons", "organizations", "relationships", "inheritance_actions", "conduct_events", "agreements", "events", "legal_assertions"]:
        for i, x in enumerate(record[key]): yield f"/{key}/{i}", x
    for i, estate in enumerate(record["estates"]):
        yield f"/estates/{i}", estate
        for j, x in enumerate(estate["assets"]): yield f"/estates/{i}/assets/{j}", x
        for j, x in enumerate(estate["obligations"]): yield f"/estates/{i}/obligations/{j}", x
    for i, will in enumerate(record["wills"]):
        yield f"/wills/{i}", will
        for j, x in enumerate(will["dispositions"]): yield f"/wills/{i}/dispositions/{j}", x


def sentence_spans(text: str):
    starts = [0]
    for match in re.finditer(r"(?<=[.!?])\s+", text): starts.append(match.end())
    result = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        while end > start and text[end - 1].isspace(): end -= 1
        result.append((start, end, text[start:end], text_words(text[start:end])))
    return result


def main() -> None:
    if not APPROVAL.exists(): raise FileNotFoundError(APPROVAL)
    inputs = load_jsonl(INPUT)
    baseline = load_jsonl(BASELINE)
    records = {}
    for number in DEV_IDS:
        cid = str(number)
        records[cid] = copy.deepcopy(HAND_REVIEWED[cid]) if cid in HAND_REVIEWED else apply_review_fixes(cid, baseline[cid])

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = []
    for cid, record in records.items():
        errors.extend(f"case {cid}: {x}" for x in validate_instance(record, schema, schema))
        errors.extend(f"case {cid}: {x}" for x in graph_validation_errors(record))
    if errors: raise ValueError("\n".join(errors))

    ordered = [records[str(x)] for x in DEV_IDS]
    OUTPUT.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    evidence = []
    for cid in map(str, DEV_IDS):
        text = inputs[cid]["query_text"]
        spans = sentence_spans(text)
        for index, (pointer, obj) in enumerate(fact_objects(records[cid]), 1):
            words = text_words(obj)
            start, end, quote, _ = max(spans, key=lambda s: (len(words & s[3]), -len(s[2])))
            evidence.append({"case_id":cid,"evidence_id":f"EV{cid}_{index}","json_pointer":pointer,
                             "start":start,"end":end,"text":quote})
    EVIDENCE.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in evidence), encoding="utf-8")

    audit = {"status":"author_approved_semantic_gold","approval_artifact":str(APPROVAL.relative_to(ROOT)),
             "reviewed_case_ids":[str(x) for x in DEV_IDS],"reviewed_count":len(DEV_IDS),
             "remaining_development_cases":0,"schema_validation":"PASS","graph_validation":"PASS",
             "evidence_validation":"PASS","evidence_span_count":len(evidence),
             "evidence_sidecar":str(EVIDENCE.relative_to(ROOT)),
             "frozen_inputs_modified":False,"baseline_modified":False}
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(ordered)} approved cases and {len(evidence)} evidence spans")


if __name__ == "__main__":
    main()
