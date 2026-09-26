#!/usr/bin/env python3
"""Build the frozen benchmark split and release-governance artifacts.

The split uses runtime inputs and temporal metadata only. It never reads
reference articles, allocations, or extraction gold.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/canonical/input.jsonl"
TEMPORAL = ROOT / "data/review/temporal_map.csv"
OUT = ROOT / "data/release"
SPLIT_VERSION = "igep-split-v1"
DEV_TARGET = 30


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"\d[\d.,/]*", " <num> ", text)
    text = re.sub(r"[^\wÀ-ỹ]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def tokens(text: str) -> set[str]:
    return {x for x in norm(text).split() if len(x) > 1 and x not in {"ông", "bà", "anh", "chị", "cụ"}}


def similarity(a: str, b: str) -> tuple[float, float]:
    ta, tb = tokens(a), tokens(b)
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    # SequenceMatcher is quadratic on long legal narratives. A sequence score
    # cannot reach the action threshold in practice when vocabulary overlap is
    # very low, so prefilter those pairs deterministically.
    seq = (
        SequenceMatcher(None, norm(a), norm(b), autojunk=True).ratio()
        if jac >= 0.35
        else 0.0
    )
    return jac, seq


def will_class(text: str) -> str:
    n = norm(text)
    has_will = "di chúc" in n
    no_will = bool(re.search(r"(không|ko) (có |để lại )?di chúc", n))
    if has_will and no_will and n.count("di chúc") > 1:
        return "mixed"
    if no_will:
        return "intestate"
    return "testate" if has_will else "not_stated"


def family_signature(text: str, opening_count: int) -> str:
    n = norm(text)
    terms = ["vợ", "chồng", "con", "cha", "mẹ", "cháu", "anh", "chị", "em", "nuôi", "ly hôn"]
    counts = [min(len(re.findall(rf"\b{re.escape(t)}\b", n)), 9) for t in terms]
    return "F" + "-".join(map(str, counts)) + f"-O{opening_count}-W{will_class(text)}"


def complexity(text: str, openings: int) -> tuple[str, int]:
    score = len(norm(text).split()) + 35 * (openings - 1)
    score += 12 * len(re.findall(r"\b(chết|mất)\b", norm(text)))
    score += 10 * len(re.findall(r"\b(di chúc|thế vị|từ chối|truất quyền)\b", norm(text)))
    return ("low" if score < 230 else "medium" if score < 390 else "high"), score


class DSU:
    def __init__(self, ids: list[str]): self.p = {x: x for x in ids}
    def find(self, x: str) -> str:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a: str, b: str) -> None:
        a, b = self.find(a), self.find(b)
        if a != b: self.p[max(a, b)] = min(a, b)


def build() -> None:
    cases = read_jsonl(INPUT)
    temporal = read_csv(TEMPORAL)
    by_case = defaultdict(list)
    for row in temporal: by_case[row["case_id"]].append(row)
    ids = [str(c["case_id"]) for c in cases]
    dsu = DSU(ids)
    pair_rows = []
    for i, a in enumerate(cases):
        for b in cases[i + 1:]:
            jac, seq = similarity(a["query_text"], b["query_text"])
            related = jac >= 0.62 or seq >= 0.78
            if related: dsu.union(str(a["case_id"]), str(b["case_id"]))
            if related or jac >= 0.48 or seq >= 0.68:
                pair_rows.append({
                    "case_id_a": a["case_id"], "case_id_b": b["case_id"],
                    "token_jaccard": f"{jac:.6f}", "sequence_similarity": f"{seq:.6f}",
                    "same_partition_required": "yes" if related else "no",
                    "audit_reason": "near_duplicate_or_shared_event" if related else "manual_similarity_review",
                })
    groups = defaultdict(list)
    for x in ids: groups[dsu.find(x)].append(x)

    metadata = {}
    for c in cases:
        cid = str(c["case_id"]); openings = by_case[cid]
        regimes = "+".join(sorted({x["candidate_regime"] for x in openings}))
        level, score = complexity(c["query_text"], len(openings))
        metadata[cid] = {
            "source_type": c["source_type"], "legal_regimes": regimes,
            "succession_mode": will_class(c["query_text"]),
            "opening_count": len(openings), "complexity": level,
            "complexity_score": score,
            "family_signature": family_signature(c["query_text"], len(openings)),
        }

    dimensions = ["source_type", "legal_regimes", "succession_mode", "complexity"]
    totals = {d: Counter(metadata[x][d] for x in ids) for d in dimensions}
    targets = {d: {k: v * DEV_TARGET / len(ids) for k, v in ct.items()} for d, ct in totals.items()}
    selected, dev_counts, dev_n = set(), {d: Counter() for d in dimensions}, 0
    remaining = set(groups)
    while dev_n < DEV_TARGET:
        options = []
        for root in remaining:
            members = groups[root]
            if dev_n + len(members) > DEV_TARGET: continue
            benefit = 0.0
            for d in dimensions:
                add = Counter(metadata[x][d] for x in members)
                before = sum(abs(dev_counts[d][k] - targets[d][k]) for k in targets[d])
                after = sum(abs(dev_counts[d][k] + add[k] - targets[d][k]) for k in targets[d])
                benefit += before - after
            tie = hashlib.sha256(f"{SPLIT_VERSION}:{root}".encode()).hexdigest()
            options.append((benefit / len(members), tie, root))
        if not options: raise RuntimeError("Cannot reach exact development size without splitting a group")
        _, _, root = max(options)
        remaining.remove(root); selected.add(root)
        for cid in groups[root]:
            dev_n += 1
            for d in dimensions: dev_counts[d][metadata[cid][d]] += 1

    split_rows, provenance = [], []
    edu_counters = Counter()
    for c in sorted(cases, key=lambda x: int(x["case_id"])):
        cid = str(c["case_id"]); m = metadata[cid]
        split = "development" if dsu.find(cid) in selected else "test"
        source = c["source"]
        if c["source_type"] == "court_judgment_derived":
            stable_source_id = f"IGEP-COURT-{int(cid):04d}"
            source_record_status = "original_judgment_identifier_missing"
        else:
            code = "HUL" if "Luật" in source and "Huế" in source else "UEL"
            edu_counters[code] += 1
            stable_source_id = f"IGEP-EDU-{code}-{edu_counters[code]:03d}"
            source_record_status = "institution_identified_item_locator_missing"
        split_rows.append({
            "case_id": cid, "split": split, "split_version": SPLIT_VERSION,
            "group_id": f"G{int(dsu.find(cid)):03d}", "stable_source_id": stable_source_id,
            **m,
        })
        provenance.append({
            "case_id": cid, "stable_source_id": stable_source_id,
            "source_type": c["source_type"], "source_locator": source,
            "source_record_status": source_record_status,
            "transformation": "sanitized_and_benchmark_adapted",
            "answer_origin": "court_adjudicated_outcome" if c["source_type"] == "court_judgment_derived" else "reviewed_educational_answer",
            "redistribution_status": "restricted_pending_source_level_clearance",
        })
    write_csv(OUT / "split.csv", split_rows)
    write_csv(OUT / "provenance.csv", provenance)
    write_csv(OUT / "overlap_pairs.csv", pair_rows or [{
        "case_id_a":"", "case_id_b":"", "token_jaccard":"", "sequence_similarity":"",
        "same_partition_required":"no", "audit_reason":"no_pairs_above_review_threshold"}])

    stats = {
        "benchmark_version": "1.0.0-frozen-candidate", "case_count": len(cases),
        "opening_count": len(temporal), "split": Counter(x["split"] for x in split_rows),
        "source_type": Counter(x["source_type"] for x in split_rows),
        "succession_mode": Counter(x["succession_mode"] for x in split_rows),
        "complexity": Counter(x["complexity"] for x in split_rows),
        "opening_count_per_case": Counter(str(x["opening_count"]) for x in split_rows),
        "legal_regime_combinations": Counter(x["legal_regimes"] for x in split_rows),
        "duplicate_groups": sum(len(v) > 1 for v in groups.values()),
        "largest_group": max(map(len, groups.values())),
    }
    (OUT / "statistics.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2, default=dict)+"\n", encoding="utf-8")
    cross = [p for p in pair_rows if p["same_partition_required"] == "yes" and next(x for x in split_rows if x["case_id"]==str(p["case_id_a"]))["split"] != next(x for x in split_rows if x["case_id"]==str(p["case_id_b"]))["split"]]
    audit = [
        "# Split and overlap audit", "", f"- Split version: `{SPLIT_VERSION}`",
        f"- Development: {sum(x['split']=='development' for x in split_rows)} cases",
        f"- Held-out test: {sum(x['split']=='test' for x in split_rows)} cases",
        f"- Related/near-duplicate groups: {stats['duplicate_groups']}",
        f"- Required same-group pairs crossing partitions: {len(cross)}", "",
        "The grouping pass uses normalized input text only. A pair is forced into the same",
        "partition at token Jaccard >= 0.62 or sequence similarity >= 0.78. Lower-scoring",
        "pairs in `overlap_pairs.csv` form a manual audit queue. Family signatures are",
        "reported for stratification diagnostics; identical generic structures alone do not",
        "prove that two cases originate from the same family or judgment.", "",
        "The split script never reads reference articles, allocations, or extraction gold.",
        "The 120-case test references must remain sealed during system development.",
    ]
    (OUT / "split_audit.md").write_text("\n".join(audit)+"\n", encoding="utf-8")

    def table(counter: Counter) -> list[str]:
        return ["| Category | Cases |", "|---|---:|"] + [
            f"| {key} | {value} |" for key, value in sorted(counter.items())
        ]
    stat_lines = [
        "# Benchmark statistics", "", "## Size", "",
        f"- Cases: {len(cases)}", f"- Succession openings: {len(temporal)}",
        f"- Development cases: {sum(x['split']=='development' for x in split_rows)}",
        f"- Held-out test cases: {sum(x['split']=='test' for x in split_rows)}",
        "", "## Source type", "",
        *table(Counter(x["source_type"] for x in split_rows)),
        "", "## Succession mode", "",
        *table(Counter(x["succession_mode"] for x in split_rows)),
        "", "## Complexity", "",
        *table(Counter(x["complexity"] for x in split_rows)),
        "", "## Number of succession openings per case", "",
        *table(Counter(str(x["opening_count"]) for x in split_rows)),
        "", "Statistics are generated from sanitized inputs and temporal metadata only.",
    ]
    (OUT / "statistics.md").write_text("\n".join(stat_lines)+"\n", encoding="utf-8")

    license_text = """# Distribution and licensing decision

Current decision: **no public redistribution of case text, labels, judgment-derived
records, or collected DOCX sources** until source-level rights and database terms
have been documented. Internal stable IDs do not replace original judgment IDs.

Code and original project documentation may be released under a separately chosen
software/documentation license. No license is assigned automatically by this build.
Metadata may be released only after checking that it does not reconstruct restricted
case content. A future public benchmark release requires written, source-by-source
clearance and a new release manifest.
"""
    (OUT / "LICENSE_DECISION.md").write_text(license_text, encoding="utf-8")

    if len(split_rows) != 150 or Counter(x["split"] for x in split_rows) != {"development": 30, "test": 120}:
        raise ValueError("Frozen split must contain exactly 30 development and 120 test cases")
    if cross:
        raise ValueError("A required related-case group crosses split boundaries")
    if len({x["stable_source_id"] for x in provenance}) != 150:
        raise ValueError("Stable source identifiers must be unique")


def checksums() -> None:
    rows = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or any(x in p.parts for x in {".git", ".venv", "__pycache__"}): continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in {".env", "data/release/checksums.csv"}: continue
        tier = "restricted" if rel.startswith("data/") and rel != "data/DATASET_CARD.md" else "public_candidate"
        rows.append({"path": rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size, "access_tier": tier})
    write_csv(OUT / "checksums.csv", rows)


def main() -> None:
    build(); checksums()
    print(f"Built release artifacts in {OUT}")


if __name__ == "__main__": main()
