#!/usr/bin/env python3
"""Evaluate final heir-and-amount predictions against reference allocations."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE = ROOT / "data/canonical/reference.jsonl"
DEFAULT_SPLIT = ROOT / "data/release/split.csv"
HONORIFIC = re.compile(r"^(?:ông|bà|cụ|anh|chị|cháu)\s+", re.I)


def load(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    value = json.loads(text) if text.lstrip().startswith("[") else [json.loads(x) for x in text.splitlines() if x]
    result = {}
    for row in value:
        cid = str(row["case_id"])
        if cid in result: raise ValueError(f"{path}: duplicate case {cid}")
        result[cid] = row
    return result


def name(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = HONORIFIC.sub("", value.strip())
    return re.sub(r"\s+", " ", value).casefold()


def allocation_map(rows, field: str):
    result = {}
    for item in rows:
        recipient = name(str(item["recipient"]))
        amount = item.get("amount")
        if isinstance(amount, float) and amount.is_integer(): amount = int(amount)
        if not isinstance(amount, int) or amount < 0:
            raise ValueError(f"invalid amount for {item.get('recipient')}: {amount}")
        if recipient in result: raise ValueError(f"duplicate normalized recipient: {recipient}")
        result[recipient] = amount
    return result


def f1(tp, predicted, gold):
    precision = tp / predicted if predicted else (1.0 if not gold else 0.0)
    recall = tp / gold if gold else (1.0 if not predicted else 0.0)
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, score


def evaluate_records(refs, preds, split: str):
    """Evaluate records while containing malformed predictions to their case."""
    cases=[]; heir_tp=heir_pred=heir_gold=amount_correct=amount_total=0
    citation_tp=citation_pred=citation_gold=0
    for cid in sorted(refs, key=int):
        ref = refs[cid]
        pred = preds.get(cid)
        # Reference errors remain fatal: silently scoring malformed gold would
        # invalidate the experiment. Prediction errors are case-local failures.
        gold_alloc = allocation_map(ref["reference_settlement"], "reference_settlement")
        if pred is None:
            cases.append({"case_id":cid,"missing":True,"invalid":False,"heir_f1":0.0,"allocation_exact":False})
            heir_gold += len(gold_alloc); citation_gold += len(set(ref["reference_articles"])); amount_total += len(gold_alloc)
            continue

        gs = set(gold_alloc)
        gc=set(map(str,ref["reference_articles"])); pc=set(map(str,pred.get("cited_articles",[])))
        citation_tp += len(gc&pc); citation_pred += len(pc); citation_gold += len(gc)
        try:
            # allocation_map deliberately rejects normalized duplicates. Do not
            # merge, deduplicate, or mutate the raw prediction.
            pred_alloc = allocation_map(pred.get("allocations", []), "allocations")
        except (KeyError, TypeError, ValueError) as exc:
            heir_gold += len(gs)
            amount_total += len(gs)
            cases.append({
                "case_id":cid,
                "missing":False,
                "invalid":True,
                "validation_errors":[str(exc)],
                "heir_f1":0.0,
                "amounts_correct":0,
                "reference_recipients":len(gs),
                "allocation_exact":False,
                "predicted_total_matches_reference":False,
                "citation_recall":len(gc&pc)/len(gc) if gc else 1.0,
            })
            continue

        ps = set(pred_alloc); common=gs&ps
        heir_tp += len(common); heir_pred += len(ps); heir_gold += len(gs)
        correct = sum(pred_alloc[x] == gold_alloc[x] for x in common)
        amount_correct += correct; amount_total += len(gs)
        _,_,case_f1=f1(len(common),len(ps),len(gs))
        exact = pred_alloc == gold_alloc
        cases.append({"case_id":cid,"missing":False,"invalid":False,"heir_f1":case_f1,
                      "amounts_correct":correct,"reference_recipients":len(gs),
                      "allocation_exact":exact,"predicted_total_matches_reference":sum(pred_alloc.values())==ref["total_reference_amount"],
                      "citation_recall":len(gc&pc)/len(gc) if gc else 1.0})
    hp,hr,hf=f1(heir_tp,heir_pred,heir_gold)
    cp,cr,cf=f1(citation_tp,citation_pred,citation_gold)
    answered=sum(not x["missing"] for x in cases)
    report={"protocol":{"split":split,"name_normalization":"NFC, trim honorific, casefold","amount_tolerance_vnd":0},
            "coverage":{"reference_cases":len(refs),"prediction_records":len(preds),"answered_cases":answered,"answer_coverage":answered/len(refs),
                        "invalid_cases":sum(x["invalid"] for x in cases)},
            "metrics":{"heir_precision":hp,"heir_recall":hr,"heir_f1":hf,
                       "amount_exact_accuracy":amount_correct/amount_total if amount_total else 1.0,
                       "allocation_exact_match":sum(x["allocation_exact"] for x in cases)/len(cases),
                       "predicted_total_matches_reference":sum(x.get("predicted_total_matches_reference",False) for x in cases)/len(cases),
                       "citation_precision":cp,"citation_recall":cr,"citation_f1":cf},"cases":cases}
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    ap.add_argument("--split", choices=["development", "test"], default="development")
    ap.add_argument("--split-manifest", type=Path, default=DEFAULT_SPLIT)
    ap.add_argument("--allow-held-out-test", action="store_true")
    ap.add_argument("--output-json", type=Path, required=True)
    ap.add_argument("--output-md", type=Path, required=True)
    args = ap.parse_args()
    if args.split == "test" and not args.allow_held_out_test:
        raise ValueError("Held-out test evaluation is locked; freeze the method first.")
    with args.split_manifest.open(encoding="utf-8-sig", newline="") as f:
        allowed = {r["case_id"] for r in csv.DictReader(f) if r["split"] == args.split}
    refs = {k:v for k,v in load(args.reference).items() if k in allowed}
    preds = {k:v for k,v in load(args.predictions).items() if k in allowed}
    report = evaluate_records(refs, preds, args.split)
    hf = report["metrics"]["heir_f1"]
    args.output_json.parent.mkdir(parents=True,exist_ok=True);args.output_md.parent.mkdir(parents=True,exist_ok=True)
    args.output_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    m=report["metrics"]
    lines=["# Final allocation evaluation","",f'- Split: `{args.split}`',f'- Cases: {len(refs)}',f'- Answer coverage: {report["coverage"]["answer_coverage"]:.4f}',f'- Invalid prediction cases: {report["coverage"]["invalid_cases"]}',"",
           "| Metric | Value |","|---|---:|",f'| Heir precision | {m["heir_precision"]:.4f} |',f'| Heir recall | {m["heir_recall"]:.4f} |',f'| Heir F1 | {m["heir_f1"]:.4f} |',f'| Amount exact accuracy | {m["amount_exact_accuracy"]:.4f} |',f'| Allocation exact match | {m["allocation_exact_match"]:.4f} |',f'| Predicted total matches reference | {m["predicted_total_matches_reference"]:.4f} |',f'| Citation precision | {m["citation_precision"]:.4f} |',f'| Citation recall | {m["citation_recall"]:.4f} |',f'| Citation F1 | {m["citation_f1"]:.4f} |',"","> This total-match diagnostic is not estate conservation. True conservation requires a separately predicted or computed net-estate amount.",""]
    args.output_md.write_text("\n".join(lines),encoding="utf-8")
    print(f"Evaluated {len(refs)} cases; heir F1={hf:.4f}; allocation exact={m['allocation_exact_match']:.4f}")


if __name__ == "__main__": main()
